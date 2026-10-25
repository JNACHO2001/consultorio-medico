"""Configuración de la aplicación, leída de variables de entorno."""
from __future__ import annotations

import os
import secrets
from dataclasses import dataclass
from datetime import time


def _booleano(valor: str | None, por_defecto: bool) -> bool:
    if valor is None:
        return por_defecto
    return valor.strip().lower() in {"1", "true", "si", "sí", "yes"}


def _hora(valor: str | None, por_defecto: time) -> time:
    if not valor:
        return por_defecto
    horas, minutos = valor.split(":")
    return time(int(horas), int(minutos))


@dataclass(frozen=True)
class Configuracion:
    secret_key: str
    zona_horaria: str = "America/Bogota"
    jornada_inicio: time = time(8, 0)
    jornada_fin: time = time(17, 0)
    duracion_cita_min: int = 30
    token_minutos: int = 30
    recordatorio_horas: int = 24
    sembrar_datos_demo: bool = True
    contrasena_demo: str = "Salud2026*"
    iteraciones_hash: int = 200_000
    recordatorios_automaticos: bool = True
    intervalo_recordatorios_seg: int = 60


def cargar_configuracion() -> Configuracion:
    """Construye la configuración a partir del entorno.

    Si no se define SECRET_KEY se genera una al arrancar: los tokens dejan de
    valer al reiniciar, lo cual es coherente con datos en memoria. En un
    despliegue real debe fijarse como variable de entorno.
    """
    return Configuracion(
        secret_key=os.getenv("SECRET_KEY") or secrets.token_urlsafe(32),
        zona_horaria=os.getenv("TZ_CONSULTORIO", "America/Bogota"),
        jornada_inicio=_hora(os.getenv("JORNADA_INICIO"), time(8, 0)),
        jornada_fin=_hora(os.getenv("JORNADA_FIN"), time(17, 0)),
        duracion_cita_min=int(os.getenv("DURACION_CITA_MIN", "30")),
        token_minutos=int(os.getenv("TOKEN_MINUTOS", "30")),
        recordatorio_horas=int(os.getenv("RECORDATORIO_HORAS", "24")),
        sembrar_datos_demo=_booleano(os.getenv("SEMBRAR_DATOS_DEMO"), True),
        contrasena_demo=os.getenv("CONTRASENA_DEMO", "Salud2026*"),
        recordatorios_automaticos=_booleano(os.getenv("RECORDATORIOS_AUTOMATICOS"), True),
    )
