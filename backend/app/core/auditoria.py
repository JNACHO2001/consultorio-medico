"""Funciones auxiliares para escribir en la bitácora de auditoría (RF-13)."""
from __future__ import annotations

from datetime import datetime, timezone

from app.core.contexto import obtener_usuario
from app.domain.modelos import RegistroAuditoria
from app.repositories.interfaces import IAuditoriaRepository


def auditar(
    auditoria: IAuditoriaRepository, entidad: str, accion: str, id_entidad: int = 0
) -> None:
    """Anota una acción del usuario de la petición actual.

    Si no hay usuario en el contexto (carga de datos demo, tareas internas)
    no se escribe nada: no hay a quién atribuir la acción.
    """
    usuario = obtener_usuario()
    if usuario is None:
        return
    auditar_como(auditoria, usuario.id, usuario.nombre_usuario, entidad, accion, id_entidad)


def auditar_como(
    auditoria: IAuditoriaRepository,
    usuario_id: int,
    usuario: str,
    entidad: str,
    accion: str,
    id_entidad: int = 0,
) -> None:
    """Anota una acción de un usuario indicado de forma explícita (por ejemplo, el inicio de sesión)."""
    auditoria.registrar(
        RegistroAuditoria(
            fecha_hora=datetime.now(timezone.utc),
            usuario_id=usuario_id,
            usuario=usuario,
            accion=accion,
            entidad=entidad,
            id_entidad=id_entidad,
        )
    )
