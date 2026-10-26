"""Endpoint de salud para monitoreo (patrón Health Endpoint Monitoring, RNF-04)."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.api.deps import contenedor
from app.container import Contenedor

router = APIRouter(tags=["Monitoreo"])


@router.get("/health", summary="Estado del sistema (sin autenticación)")
def estado(c: Contenedor = Depends(contenedor)) -> JSONResponse:
    """Verifica que cada repositorio responde. Un balanceador o servicio de monitoreo
    de la nube puede consultarlo periódicamente. No expone datos de pacientes."""
    comprobaciones = {
        "usuarios": c.repo_usuarios.listar,
        "citas": c.repo_citas.listar,
        "recordatorios": c.repo_recordatorios.listar,
    }
    componentes = {}
    for nombre, comprobar in comprobaciones.items():
        try:
            comprobar()
            componentes[nombre] = "ok"
        except Exception:  # noqa: BLE001 - cualquier fallo del repositorio degrada el estado
            componentes[nombre] = "falla"
    sano = all(v == "ok" for v in componentes.values())
    return JSONResponse(
        status_code=200 if sano else 503,
        content={
            "estado": "ok" if sano else "degradado",
            "componentes": componentes,
            "hora_servidor": datetime.now(timezone.utc).isoformat(),
        },
    )
