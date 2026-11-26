"""Estrategias de búsqueda del catálogo CIE-10 (patrón Strategy).

La navegación por el catálogo de diagnósticos es el punto del sistema donde el
usuario escribe letra a letra y espera respuesta inmediata. Con la muestra de
149 códigos cualquier implementación sirve; con el catálogo oficial (más de
12.000 códigos) la diferencia entre recorrer la lista completa en cada pulsación
y consultar un índice invertido se vuelve perceptible.

Las dos estrategias cumplen la misma interfaz, de modo que `Cie10Service` puede
cambiar de una a otra sin tocar la API ni el frontend. La medición está en
``benchmarks/benchmark_navegacion.py``.
"""
from __future__ import annotations

import unicodedata
from abc import ABC, abstractmethod
from collections import defaultdict
from typing import Iterator, Optional


def normalizar(texto: str) -> str:
    """Minúsculas sin tildes: «Diabetes mellitus» y «diabetes» coinciden."""
    descompuesto = unicodedata.normalize("NFKD", texto or "")
    return "".join(c for c in descompuesto if not unicodedata.combining(c)).lower().strip()


def tokenizar(texto: str) -> list[str]:
    limpio = normalizar(texto).replace(".", " ").replace(",", " ").replace("[", " ").replace("]", " ")
    return [t for t in limpio.split() if t]


class EstrategiaBusqueda(ABC):
    """Contrato común: dado un catálogo, resolver una consulta del usuario."""

    nombre = "abstracta"

    def __init__(self, catalogo: list[tuple[str, str]]) -> None:
        self._catalogo = catalogo

    @abstractmethod
    def buscar(self, consulta: str) -> Iterator[tuple[int, str, str]]:
        """Devuelve (prioridad, código, descripción). Prioridad 0 = coincide el código."""

    def descripcion(self, codigo: str) -> Optional[str]:
        raise NotImplementedError


class BusquedaSecuencial(EstrategiaBusqueda):
    """Recorre el catálogo completo en cada consulta: O(n · t) por pulsación.

    Es la implementación original del sistema. Se conserva porque es la
    referencia contra la cual se mide la mejora, y porque para catálogos
    pequeños evita el costo de construir y mantener un índice.
    """

    nombre = "secuencial"

    def __init__(self, catalogo: list[tuple[str, str]]) -> None:
        super().__init__(catalogo)
        self._por_codigo = {codigo: descripcion for codigo, descripcion in catalogo}
        self._indice = [(c, d, normalizar(c + " " + d)) for c, d in catalogo]

    def buscar(self, consulta: str) -> Iterator[tuple[int, str, str]]:
        palabras = tokenizar(consulta)
        if not palabras:
            return iter(())
        return self._recorrer(palabras)

    def _recorrer(self, palabras: list[str]) -> Iterator[tuple[int, str, str]]:
        for codigo, descripcion, texto in self._indice:
            if all(p in texto for p in palabras):
                prioridad = 0 if codigo.lower().startswith(palabras[0]) else 1
                yield (prioridad, codigo, descripcion)

    def descripcion(self, codigo: str) -> Optional[str]:
        return self._por_codigo.get((codigo or "").strip().upper())


class BusquedaIndiceInvertido(EstrategiaBusqueda):
    """Índice invertido con prefijos: el costo depende del término, no del catálogo.

    Se construye una sola vez al arrancar. Para cada palabra de la descripción se
    guardan todos sus prefijos, de modo que «diab» encuentra «diabetes» sin
    recorrer las 12.000 entradas. La consulta interseca las listas de las
    palabras escritas y empieza por la más corta, que es la que más filtra.
    """

    nombre = "indice"
    PREFIJO_MAXIMO = 12  # más allá no aporta y agranda el índice

    def __init__(self, catalogo: list[tuple[str, str]]) -> None:
        super().__init__(catalogo)
        self._por_codigo = {codigo: descripcion for codigo, descripcion in catalogo}
        self._entradas: list[tuple[str, str]] = list(catalogo)
        self._postings: dict[str, set[int]] = defaultdict(set)
        self._codigos_norm: list[str] = []
        for i, (codigo, descripcion) in enumerate(catalogo):
            self._codigos_norm.append(normalizar(codigo))
            for palabra in tokenizar(codigo + " " + descripcion):
                for largo in range(1, min(len(palabra), self.PREFIJO_MAXIMO) + 1):
                    self._postings[palabra[:largo]].add(i)

    @property
    def tamano_indice(self) -> int:
        return len(self._postings)

    def buscar(self, consulta: str) -> Iterator[tuple[int, str, str]]:
        palabras = tokenizar(consulta)
        if not palabras:
            return iter(())
        listas = []
        for palabra in palabras:
            clave = palabra[: self.PREFIJO_MAXIMO]
            encontrados = self._postings.get(clave)
            if not encontrados:
                return iter(())  # una palabra sin resultados anula la consulta
            listas.append(encontrados)
        listas.sort(key=len)  # intersecar desde la lista más corta
        resultado = set(listas[0])
        for otra in listas[1:]:
            resultado &= otra
            if not resultado:
                return iter(())
        return self._ordenar(resultado, palabras[0])

    def _ordenar(self, indices: set[int], primera: str) -> Iterator[tuple[int, str, str]]:
        for i in sorted(indices):
            codigo, descripcion = self._entradas[i]
            prioridad = 0 if self._codigos_norm[i].startswith(primera) else 1
            yield (prioridad, codigo, descripcion)

    def descripcion(self, codigo: str) -> Optional[str]:
        return self._por_codigo.get((codigo or "").strip().upper())


ESTRATEGIAS: dict[str, type[EstrategiaBusqueda]] = {
    BusquedaSecuencial.nombre: BusquedaSecuencial,
    BusquedaIndiceInvertido.nombre: BusquedaIndiceInvertido,
}
