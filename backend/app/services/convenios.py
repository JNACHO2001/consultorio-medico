"""Pagadores (EPS, ARL, particular…) y convenios con sus tarifas y copagos (RF-19)."""
from __future__ import annotations

import re
import threading
from typing import Optional

from app.domain.excepciones import Duplicado, NoEncontrado, ReglaNegocio
from app.domain.modelos import Convenio, Pagador, TipoPagador
from app.repositories.interfaces import IConvenioRepository, IPagadorRepository

CODIGO_PARTICULAR = "PARTICULAR"
PORCENTAJE_TARIFA_MAXIMO = 300
CUOTA_MODERADORA_MAXIMA = 1_000_000
_PATRON_CODIGO = re.compile(r"^[A-Z0-9-]{2,12}$")


def calcular_precio(tarifa_base: int, convenio: Optional[Convenio]) -> int:
    """Tarifa base ajustada por el convenio, en pesos enteros (redondeo al peso más cercano)."""
    if convenio is None:
        return tarifa_base
    return (tarifa_base * convenio.porcentaje_tarifa + 50) // 100


def repartir_total(total: int, convenio: Optional[Convenio]) -> tuple[int, int]:
    """Divide una cuenta en lo que paga el paciente y lo que paga el pagador (RN-15).

    El paciente asume el copago porcentual más la cuota moderadora, sin pasar del total.
    Sin convenio, o con el particular, el paciente paga todo.
    """
    if convenio is None:
        return total, 0
    copago = (total * convenio.copago_porcentaje + 50) // 100
    paciente = min(total, copago + convenio.cuota_moderadora)
    return paciente, total - paciente


def _entero(valor: object, nombre: str, minimo: int, maximo: int) -> int:
    if not isinstance(valor, int) or isinstance(valor, bool) or not minimo <= valor <= maximo:
        raise ReglaNegocio(f"{nombre} debe ser un entero entre {minimo} y {maximo}.")
    return valor


class ConvenioService:
    def __init__(self, pagadores: IPagadorRepository, convenios: IConvenioRepository) -> None:
        self._pagadores = pagadores
        self._convenios = convenios
        self._lock = threading.Lock()

    # ------------------------------------------------------------ el particular

    def asegurar_particular(self) -> Convenio:
        """Crea, si no existe, el pagador particular con su convenio fijo (el paciente paga todo)."""
        with self._lock:
            pagador = self._pagadores.obtener_por_codigo(CODIGO_PARTICULAR)
            if pagador is None:
                pagador = self._pagadores.agregar(
                    Pagador(codigo=CODIGO_PARTICULAR, nombre="Particular", tipo=TipoPagador.PARTICULAR)
                )
            existentes = self._convenios.obtener_por_pagador(pagador.id)
            if existentes:
                return existentes[0]
            return self._convenios.agregar(
                Convenio(pagador_id=pagador.id, nombre="Tarifa particular", copago_porcentaje=100)
            )

    def particular(self) -> Convenio:
        return self.asegurar_particular()

    # ----------------------------------------------------------------- pagadores

    def listar_pagadores(self) -> list[Pagador]:
        return sorted(self._pagadores.listar(), key=lambda p: (p.tipo != TipoPagador.PARTICULAR, p.nombre.lower()))

    def obtener_pagador(self, pagador_id: int, incluir_inactivo: bool = False) -> Pagador:
        for pagador in self._pagadores.listar(incluir_inactivos=incluir_inactivo):
            if pagador.id == pagador_id:
                return pagador
        raise NoEncontrado("El pagador no existe.")

    def crear_pagador(self, codigo: str, nombre: str, tipo: TipoPagador, nit: str = "") -> Pagador:
        codigo = (codigo or "").strip().upper()
        nombre = (nombre or "").strip()
        if not _PATRON_CODIGO.match(codigo):
            raise ReglaNegocio("El código debe tener entre 2 y 12 letras mayúsculas, números o guiones.")
        if not nombre:
            raise ReglaNegocio("El nombre del pagador es obligatorio.")
        if tipo == TipoPagador.PARTICULAR:
            raise ReglaNegocio("El pagador particular ya existe y no se puede crear otro.")
        with self._lock:
            if self._pagadores.obtener_por_codigo(codigo):
                raise Duplicado("Ya existe un pagador con ese código.")
            return self._pagadores.agregar(
                Pagador(codigo=codigo, nombre=nombre, tipo=tipo, nit=(nit or "").strip())
            )

    def actualizar_pagador(
        self, pagador_id: int, nombre: Optional[str] = None, nit: Optional[str] = None
    ) -> Pagador:
        pagador = self.obtener_pagador(pagador_id)
        if nombre is not None:
            nombre = nombre.strip()
            if not nombre:
                raise ReglaNegocio("El nombre del pagador es obligatorio.")
            pagador.nombre = nombre
        if nit is not None:
            pagador.nit = nit.strip()
        return self._pagadores.actualizar(pagador)

    def desactivar_pagador(self, pagador_id: int) -> None:
        """Lo retira de la admisión sin borrarlo; sus facturas y su cartera se conservan."""
        pagador = self.obtener_pagador(pagador_id)
        if pagador.tipo == TipoPagador.PARTICULAR:
            raise ReglaNegocio("El pagador particular no se puede desactivar.")
        for convenio in self._convenios.obtener_por_pagador(pagador_id):
            self._convenios.desactivar(convenio.id)
        self._pagadores.desactivar(pagador_id)

    # ----------------------------------------------------------------- convenios

    def listar_convenios(self, pagador_id: Optional[int] = None) -> list[Convenio]:
        if pagador_id is not None:
            return self._convenios.obtener_por_pagador(pagador_id)
        return self._convenios.listar()

    def obtener_convenio(self, convenio_id: int, incluir_inactivo: bool = True) -> Convenio:
        """Por defecto encuentra también convenios retirados: lo ya admitido o facturado sigue existiendo."""
        for convenio in self._convenios.listar(incluir_inactivos=incluir_inactivo):
            if convenio.id == convenio_id:
                return convenio
        raise NoEncontrado("El convenio no existe.")

    def crear_convenio(
        self,
        pagador_id: int,
        nombre: str,
        porcentaje_tarifa: int = 100,
        copago_porcentaje: int = 0,
        cuota_moderadora: int = 0,
        requiere_autorizacion: bool = False,
    ) -> Convenio:
        pagador = self.obtener_pagador(pagador_id)
        if pagador.tipo == TipoPagador.PARTICULAR:
            raise ReglaNegocio("El pagador particular tiene un único convenio fijo.")
        nombre = (nombre or "").strip()
        if not nombre:
            raise ReglaNegocio("El nombre del convenio es obligatorio.")
        return self._convenios.agregar(
            Convenio(
                pagador_id=pagador.id,
                nombre=nombre,
                porcentaje_tarifa=_entero(porcentaje_tarifa, "El porcentaje de tarifa", 1, PORCENTAJE_TARIFA_MAXIMO),
                copago_porcentaje=_entero(copago_porcentaje, "El copago", 0, 100),
                cuota_moderadora=_entero(cuota_moderadora, "La cuota moderadora", 0, CUOTA_MODERADORA_MAXIMA),
                requiere_autorizacion=bool(requiere_autorizacion),
            )
        )

    def actualizar_convenio(
        self,
        convenio_id: int,
        nombre: Optional[str] = None,
        porcentaje_tarifa: Optional[int] = None,
        copago_porcentaje: Optional[int] = None,
        cuota_moderadora: Optional[int] = None,
        requiere_autorizacion: Optional[bool] = None,
    ) -> Convenio:
        """Los cambios rigen para lo que se registre desde ahora; lo ya facturado no cambia (RN-14)."""
        convenio = self.obtener_convenio(convenio_id)
        if self.obtener_pagador(convenio.pagador_id, incluir_inactivo=True).tipo == TipoPagador.PARTICULAR:
            raise ReglaNegocio("El convenio del pagador particular es fijo.")
        if nombre is not None:
            nombre = nombre.strip()
            if not nombre:
                raise ReglaNegocio("El nombre del convenio es obligatorio.")
            convenio.nombre = nombre
        if porcentaje_tarifa is not None:
            convenio.porcentaje_tarifa = _entero(porcentaje_tarifa, "El porcentaje de tarifa", 1, PORCENTAJE_TARIFA_MAXIMO)
        if copago_porcentaje is not None:
            convenio.copago_porcentaje = _entero(copago_porcentaje, "El copago", 0, 100)
        if cuota_moderadora is not None:
            convenio.cuota_moderadora = _entero(cuota_moderadora, "La cuota moderadora", 0, CUOTA_MODERADORA_MAXIMA)
        if requiere_autorizacion is not None:
            convenio.requiere_autorizacion = bool(requiere_autorizacion)
        return self._convenios.actualizar(convenio)

    def desactivar_convenio(self, convenio_id: int) -> None:
        convenio = self.obtener_convenio(convenio_id)
        if self.obtener_pagador(convenio.pagador_id, incluir_inactivo=True).tipo == TipoPagador.PARTICULAR:
            raise ReglaNegocio("El convenio del pagador particular no se puede desactivar.")
        self._convenios.desactivar(convenio_id)
