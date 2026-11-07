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
    # Datos de la IPS que van en el encabezado del RIPS (valores de demostración).
    ips_nombre: str = "Salud Integral (demostración)"
    ips_nit: str = "900000000-0"
    ips_codigo_habilitacion: str = "0000000000"
    # Facturación electrónica. Los valores por defecto son los del ambiente de pruebas (habilitación).
    dian_ambiente: str = "2"  # 1 producción, 2 pruebas
    dian_prefijo: str = "SETP"
    dian_resolucion: str = "18760000001"
    dian_rango_desde: int = 990000000
    dian_rango_hasta: int = 995000000
    dian_clave_tecnica: str = "fc8eac422eba16e22ffd8c6f94b3f40a6e38162c"
    dian_pin_software: str = "75315"
    dian_obligatoria: bool = True  # RN-20: no se radica una factura sin factura electrónica aceptada
    caja_obligatoria: bool = True  # RN-23: el cajero necesita una caja abierta para cobrar al paciente


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
        ips_nombre=os.getenv("IPS_NOMBRE", "Salud Integral (demostración)"),
        ips_nit=os.getenv("IPS_NIT", "900000000-0"),
        ips_codigo_habilitacion=os.getenv("IPS_CODIGO_HABILITACION", "0000000000"),
        dian_ambiente=os.getenv("DIAN_AMBIENTE", "2"),
        dian_prefijo=os.getenv("DIAN_PREFIJO", "SETP"),
        dian_resolucion=os.getenv("DIAN_RESOLUCION", "18760000001"),
        dian_rango_desde=int(os.getenv("DIAN_RANGO_DESDE", "990000000")),
        dian_rango_hasta=int(os.getenv("DIAN_RANGO_HASTA", "995000000")),
        dian_clave_tecnica=os.getenv("DIAN_CLAVE_TECNICA", "fc8eac422eba16e22ffd8c6f94b3f40a6e38162c"),
        dian_pin_software=os.getenv("DIAN_PIN_SOFTWARE", "75315"),
        dian_obligatoria=_booleano(os.getenv("DIAN_OBLIGATORIA"), True),
        caja_obligatoria=_booleano(os.getenv("CAJA_OBLIGATORIA"), True),
    )
