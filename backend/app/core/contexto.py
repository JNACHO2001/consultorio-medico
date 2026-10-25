"""Usuario que ejecuta la petición actual.

Los repositorios lo leen para registrar en la bitácora quién consultó o
modificó cada dato (RF-13) sin que los servicios tengan que pasarlo en cada
llamada. Si no hay usuario (carga de datos demo, tareas internas) no se audita.
"""
from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass
from typing import Optional

from app.domain.modelos import Rol


@dataclass(frozen=True)
class UsuarioContexto:
    id: int
    nombre_usuario: str
    rol: Rol


_usuario_actual: ContextVar[Optional[UsuarioContexto]] = ContextVar("usuario_actual", default=None)


def establecer_usuario(usuario: Optional[UsuarioContexto]) -> None:
    _usuario_actual.set(usuario)


def obtener_usuario() -> Optional[UsuarioContexto]:
    return _usuario_actual.get()
