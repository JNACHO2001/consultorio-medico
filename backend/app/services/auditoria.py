"""Consulta de la bitácora de auditoría (CU-12, RF-13)."""
from __future__ import annotations

from typing import Optional

from app.domain.excepciones import ReglaNegocio
from app.domain.modelos import RegistroAuditoria
from app.repositories.interfaces import IAuditoriaRepository


class AuditoriaService:
    def __init__(self, auditoria: IAuditoriaRepository) -> None:
        self._auditoria = auditoria

    def consultar(
        self,
        usuario: Optional[str] = None,
        entidad: Optional[str] = None,
        accion: Optional[str] = None,
        limite: int = 200,
    ) -> list[RegistroAuditoria]:
        if not 1 <= limite <= 1000:
            raise ReglaNegocio("El límite debe estar entre 1 y 1000 registros.")
        return self._auditoria.consultar(usuario, entidad, accion, limite)
