"""Manejo de la hora local del consultorio.

Las citas y consultas usan la hora local del consultorio sin zona horaria
(datetime "ingenuo"); el servidor en la nube suele estar en UTC, por eso se
convierte con la zona configurada.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo


def ahora_local(zona_horaria: str) -> datetime:
    return datetime.now(ZoneInfo(zona_horaria)).replace(tzinfo=None, microsecond=0)


def a_hora_local(valor: datetime, zona_horaria: str) -> datetime:
    """Convierte un datetime con zona a hora local sin zona; uno sin zona se deja igual."""
    if valor.tzinfo is None:
        return valor
    return valor.astimezone(ZoneInfo(zona_horaria)).replace(tzinfo=None)
