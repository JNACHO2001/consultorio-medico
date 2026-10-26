"""Catálogo de procedimientos y tarifas (RF-17)."""
from __future__ import annotations

import re
import threading
from typing import Optional

from app.domain.excepciones import Duplicado, NoEncontrado, ReglaNegocio
from app.domain.modelos import Procedimiento
from app.repositories.interfaces import IProcedimientoRepository

TARIFA_MAXIMA = 100_000_000
_PATRON_CODIGO = re.compile(r"^[A-Z0-9-]{2,12}$")


def validar_tarifa(tarifa: int) -> int:
    if not isinstance(tarifa, int) or isinstance(tarifa, bool) or not 0 < tarifa <= TARIFA_MAXIMA:
        raise ReglaNegocio(f"La tarifa debe ser un valor entero en pesos entre 1 y {TARIFA_MAXIMA:,}.".replace(",", "."))
    return tarifa


class CatalogoService:
    def __init__(self, procedimientos: IProcedimientoRepository) -> None:
        self._procedimientos = procedimientos
        self._lock = threading.Lock()

    def listar(self) -> list[Procedimiento]:
        return sorted(self._procedimientos.listar(), key=lambda p: p.nombre.lower())

    def obtener(self, procedimiento_id: int) -> Procedimiento:
        procedimiento = self._procedimientos.obtener_por_id(procedimiento_id)
        if procedimiento is None:
            raise NoEncontrado("El procedimiento no existe en el catálogo.")
        return procedimiento

    def crear(self, codigo: str, nombre: str, tarifa: int) -> Procedimiento:
        codigo = (codigo or "").strip().upper()
        nombre = (nombre or "").strip()
        if not _PATRON_CODIGO.match(codigo):
            raise ReglaNegocio("El código debe tener entre 2 y 12 letras mayúsculas, números o guiones.")
        if not nombre:
            raise ReglaNegocio("El nombre del procedimiento es obligatorio.")
        validar_tarifa(tarifa)
        with self._lock:
            if self._procedimientos.obtener_por_codigo(codigo):
                raise Duplicado("Ya existe un procedimiento con ese código.")
            return self._procedimientos.agregar(Procedimiento(codigo=codigo, nombre=nombre, tarifa=tarifa))

    def actualizar(
        self, procedimiento_id: int, nombre: Optional[str] = None, tarifa: Optional[int] = None
    ) -> Procedimiento:
        """Cambia nombre o tarifa. Lo ya realizado conserva su valor original (RN-10)."""
        procedimiento = self.obtener(procedimiento_id)
        if nombre is not None:
            nombre = nombre.strip()
            if not nombre:
                raise ReglaNegocio("El nombre del procedimiento es obligatorio.")
            procedimiento.nombre = nombre
        if tarifa is not None:
            procedimiento.tarifa = validar_tarifa(tarifa)
        return self._procedimientos.actualizar(procedimiento)

    def desactivar(self, procedimiento_id: int) -> None:
        """Lo retira del catálogo sin borrarlo: lo ya realizado sigue mostrándose."""
        self.obtener(procedimiento_id)
        self._procedimientos.desactivar(procedimiento_id)
