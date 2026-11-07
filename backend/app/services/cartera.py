"""Cartera de los pagadores: radicación, abonos y glosas (RF-20, RF-21).

Cuando hay convenio, la factura se divide en lo que paga el paciente (se cobra en caja,
ver FacturacionService.pagar) y lo que debe el pagador. Esta parte sigue lo que el pagador
debe: se radica la factura, se registran sus abonos y se gestionan las glosas.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from app.config import Configuracion
from app.core.tiempo import ahora_local
from app.domain.excepciones import NoEncontrado, ReglaNegocio
from app.domain.modelos import (
    ConceptoGlosa,
    EstadoFactura,
    EstadoGlosa,
    Factura,
    Glosa,
    MetodoPago,
    OrigenPago,
    PagoFactura,
    Usuario,
)
from app.repositories.interfaces import IFacturaRepository
from app.services.facturacion import FacturacionService

TRAMOS = ("sin_radicar", "d0_30", "d31_60", "d61_90", "d_mas_90")


@dataclass
class ResumenCartera:
    pagador_id: int
    pagador_nombre: str
    n_facturas: int = 0
    facturado: int = 0
    recaudado: int = 0
    glosa_aceptada: int = 0
    en_disputa: int = 0
    saldo: int = 0
    tramos: dict[str, int] = field(default_factory=lambda: {t: 0 for t in TRAMOS})


def tramo_de_edad(dias: int) -> str:
    if dias <= 30:
        return "d0_30"
    if dias <= 60:
        return "d31_60"
    if dias <= 90:
        return "d61_90"
    return "d_mas_90"


class CarteraService:
    def __init__(
        self, facturacion: FacturacionService, facturas: IFacturaRepository, config: Configuracion
    ) -> None:
        self._facturacion = facturacion
        self._facturas = facturas
        self._config = config
        self._lock = facturacion.bloqueo

    def _ahora(self) -> datetime:
        return ahora_local(self._config.zona_horaria)

    def _a_cargo_del_pagador(self, factura_id: int, accion: str) -> Factura:
        factura = self._facturacion.obtener(factura_id)
        if factura.estado != EstadoFactura.EMITIDA:
            raise ReglaNegocio(f"La factura está {factura.estado.value.lower()}: no se puede {accion}.")
        if factura.valor_pagador <= 0:
            raise ReglaNegocio("La factura no tiene valor a cargo de un pagador.")
        return factura

    def _cerrar_si_saldada(self, factura: Factura, metodo: Optional[MetodoPago] = None) -> None:
        if factura.saldada():
            factura.estado = EstadoFactura.PAGADA
            factura.fecha_pago = self._ahora()
            if metodo is not None:
                factura.metodo_pago = metodo

    # ------------------------------------------------------------------ radicación

    def radicar(self, factura_id: int, numero: str = "") -> Factura:
        """Entrega la factura al pagador. Desde ahí corre su antigüedad y ya no se puede anular (RN-17)."""
        with self._lock:
            factura = self._a_cargo_del_pagador(factura_id, "radicar")
            if factura.radicada:
                raise ReglaNegocio("La factura ya fue radicada.")
            ahora = self._ahora()
            factura.fecha_radicacion = ahora
            factura.numero_radicacion = (numero or "").strip() or f"RAD-{ahora.year}-{factura.id:05d}"
            return self._facturas.actualizar(factura)

    # --------------------------------------------------------------------- abonos

    def registrar_pago_pagador(
        self,
        factura_id: int,
        valor: int,
        usuario: Usuario,
        metodo: MetodoPago = MetodoPago.TRANSFERENCIA,
        referencia: str = "",
    ) -> Factura:
        """Abono del pagador. Solo sobre lo que no está glosado y no excede el saldo (RN-18)."""
        with self._lock:
            factura = self._a_cargo_del_pagador(factura_id, "registrar pagos del pagador")
            if not factura.radicada:
                raise ReglaNegocio("Radique la factura antes de registrar pagos del pagador.")
            pagable = factura.saldo_pagador - factura.glosa_en_disputa
            if not isinstance(valor, int) or isinstance(valor, bool) or valor <= 0:
                raise ReglaNegocio("El valor del pago debe ser un entero mayor que cero.")
            if valor > pagable:
                raise ReglaNegocio(
                    f"El pago excede lo cobrable: el pagador debe {pagable:,} sin contar las glosas en disputa.".replace(",", ".")
                )
            factura.pagos.append(
                PagoFactura(
                    origen=OrigenPago.PAGADOR,
                    metodo=metodo,
                    valor=valor,
                    fecha=self._ahora(),
                    referencia=(referencia or "").strip(),
                    registrado_por_id=usuario.id,
                )
            )
            self._cerrar_si_saldada(factura, metodo)
            return self._facturas.actualizar(factura)

    # ---------------------------------------------------------------------- glosas

    def registrar_glosa(
        self, factura_id: int, concepto: ConceptoGlosa, motivo: str, valor: int
    ) -> Factura:
        """El pagador objeta una parte de la factura. Se registra sobre factura radicada (RN-19)."""
        motivo = (motivo or "").strip()
        if not motivo:
            raise ReglaNegocio("Indique el motivo de la glosa.")
        with self._lock:
            factura = self._a_cargo_del_pagador(factura_id, "registrar glosas")
            if not factura.radicada:
                raise ReglaNegocio("Solo se registran glosas sobre facturas radicadas.")
            libre = factura.saldo_pagador - factura.glosa_en_disputa
            if not isinstance(valor, int) or isinstance(valor, bool) or valor <= 0:
                raise ReglaNegocio("El valor de la glosa debe ser un entero mayor que cero.")
            if valor > libre:
                raise ReglaNegocio(
                    f"El valor de la glosa excede lo que se puede glosar ({libre:,}).".replace(",", ".")
                )
            siguiente = max((g.id for g in factura.glosas), default=0) + 1
            factura.glosas.append(
                Glosa(id=siguiente, concepto=concepto, motivo=motivo, valor=valor, fecha=self._ahora())
            )
            return self._facturas.actualizar(factura)

    def _glosa(self, factura: Factura, glosa_id: int) -> Glosa:
        for glosa in factura.glosas:
            if glosa.id == glosa_id:
                return glosa
        raise NoEncontrado("La glosa no existe en esta factura.")

    def responder_glosa(self, factura_id: int, glosa_id: int, respuesta: str) -> Factura:
        """La IPS sustenta por qué el cobro es correcto; queda pendiente la decisión del pagador."""
        respuesta = (respuesta or "").strip()
        if not respuesta:
            raise ReglaNegocio("Escriba la respuesta a la glosa.")
        with self._lock:
            factura = self._facturacion.obtener(factura_id)
            glosa = self._glosa(factura, glosa_id)
            if glosa.estado != EstadoGlosa.ABIERTA:
                raise ReglaNegocio(f"La glosa está {glosa.estado.value.lower()}: solo se responden las abiertas.")
            glosa.estado = EstadoGlosa.RESPONDIDA
            glosa.respuesta = respuesta
            glosa.fecha_respuesta = self._ahora()
            return self._facturas.actualizar(factura)

    def resolver_glosa(
        self, factura_id: int, glosa_id: int, aceptada: bool, nota: str = ""
    ) -> Factura:
        """Cierra la glosa: aceptada (la IPS pierde ese valor) o levantada (el pagador debe pagarlo)."""
        with self._lock:
            factura = self._facturacion.obtener(factura_id)
            glosa = self._glosa(factura, glosa_id)
            if glosa.estado not in (EstadoGlosa.ABIERTA, EstadoGlosa.RESPONDIDA):
                raise ReglaNegocio(f"La glosa ya está {glosa.estado.value.lower()}.")
            glosa.estado = EstadoGlosa.ACEPTADA if aceptada else EstadoGlosa.LEVANTADA
            glosa.nota_resolucion = (nota or "").strip()
            glosa.fecha_resolucion = self._ahora()
            self._cerrar_si_saldada(factura)
            return self._facturas.actualizar(factura)

    # --------------------------------------------------------------------- consulta

    def edad_dias(self, factura: Factura) -> Optional[int]:
        """Días desde la radicación; None si todavía no se radica."""
        if factura.fecha_radicacion is None:
            return None
        return max(0, (self._ahora().date() - factura.fecha_radicacion.date()).days)

    def facturas_del_pagador(self, pagador_id: Optional[int] = None) -> list[Factura]:
        """Facturas vigentes con valor a cargo de un pagador (de todos, o del indicado)."""
        return [
            f
            for f in self._facturas.buscar()
            if f.estado != EstadoFactura.ANULADA
            and f.valor_pagador > 0
            and (pagador_id is None or f.pagador_id == pagador_id)
        ]

    def resumen(self) -> list[ResumenCartera]:
        por_pagador: dict[int, ResumenCartera] = {}
        for factura in self.facturas_del_pagador():
            fila = por_pagador.setdefault(
                factura.pagador_id or 0, ResumenCartera(factura.pagador_id or 0, factura.pagador_nombre)
            )
            fila.n_facturas += 1
            fila.facturado += factura.valor_pagador
            fila.recaudado += factura.pagado(OrigenPago.PAGADOR)
            fila.glosa_aceptada += factura.glosado_aceptado
            fila.en_disputa += factura.glosa_en_disputa
            saldo = factura.saldo_pagador
            fila.saldo += saldo
            if saldo > 0:
                dias = self.edad_dias(factura)
                fila.tramos["sin_radicar" if dias is None else tramo_de_edad(dias)] += saldo
        return sorted(por_pagador.values(), key=lambda r: r.pagador_nombre.lower())
