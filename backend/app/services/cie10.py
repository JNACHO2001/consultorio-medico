"""Consulta del catálogo CIE-10 (RF-23).

La resolución de la consulta se delega en una *estrategia de búsqueda*
(``app.services.busqueda``). El servicio y la API no cambian cuando se cambia la
estrategia: el índice invertido se eligió como valor por omisión después de
medir ambas con el catálogo a escala real (ver ``benchmarks/benchmark_navegacion.py``).
"""
from __future__ import annotations

from typing import Optional

from app.data.cie10 import CIE10
from app.services.busqueda import BusquedaIndiceInvertido, EstrategiaBusqueda


class Cie10Service:
    def __init__(
        self,
        catalogo: list[tuple[str, str]] = CIE10,
        estrategia: Optional[EstrategiaBusqueda] = None,
    ) -> None:
        self._estrategia = estrategia or BusquedaIndiceInvertido(catalogo)

    @property
    def estrategia(self) -> str:
        return self._estrategia.nombre

    def descripcion(self, codigo: str) -> Optional[str]:
        return self._estrategia.descripcion(codigo)

    def buscar(self, consulta: str, limite: int = 20) -> list[tuple[str, str]]:
        """Busca por código (prefijo) o por palabras de la descripción, sin distinguir tildes.

        El recorte a `limite` se hace sobre un iterador perezoso: los resultados
        que no caben en la página nunca se construyen.
        """
        encontrados = sorted(self._estrategia.buscar(consulta), key=lambda t: (t[0], t[1]))
        return [(codigo, descripcion) for _, codigo, descripcion in encontrados[:limite]]
