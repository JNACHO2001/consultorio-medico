"""Consulta del catálogo CIE-10 (RF-23)."""
from __future__ import annotations

import unicodedata
from typing import Optional

from app.data.cie10 import CIE10


def _normalizar(texto: str) -> str:
    descompuesto = unicodedata.normalize("NFKD", texto or "")
    return "".join(c for c in descompuesto if not unicodedata.combining(c)).lower().strip()


class Cie10Service:
    def __init__(self, catalogo: list[tuple[str, str]] = CIE10) -> None:
        self._por_codigo = {codigo: descripcion for codigo, descripcion in catalogo}
        self._indice = [(codigo, descripcion, _normalizar(codigo + " " + descripcion)) for codigo, descripcion in catalogo]

    def descripcion(self, codigo: str) -> Optional[str]:
        return self._por_codigo.get((codigo or "").strip().upper())

    def buscar(self, consulta: str, limite: int = 20) -> list[tuple[str, str]]:
        """Busca por código (prefijo) o por palabras de la descripción, sin distinguir tildes."""
        palabras = _normalizar(consulta).replace(".", "").split()
        if not palabras:
            return []
        encontrados = []
        for codigo, descripcion, texto in self._indice:
            if all(p in texto for p in palabras):
                prioridad = 0 if codigo.lower().startswith(palabras[0]) else 1
                encontrados.append((prioridad, codigo, descripcion))
        encontrados.sort()
        return [(c, d) for _, c, d in encontrados[:limite]]
