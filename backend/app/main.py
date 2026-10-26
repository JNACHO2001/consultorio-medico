"""Punto de entrada de la API.

Ejecutar (desde la carpeta backend):

    uvicorn app.main:crear_app --factory --reload

Documentación interactiva de la API: http://localhost:8000/docs
"""
import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles

from app.api.errores import registrar_manejadores
from app.api.routers import auditoria, auth, citas, consultas, medicos, pacientes, recordatorios, salud, usuarios
from app.config import Configuracion, cargar_configuracion
from app.container import Contenedor, crear_contenedor
from app.core.tiempo import ahora_local
from app.seed import sembrar_datos_demo

registro = logging.getLogger("consultorio")

DESCRIPCION = """
Prototipo del sistema de gestión del consultorio **Salud Integral**: pacientes, agenda de citas,
historia clínica, usuarios con roles y bitácora de auditoría.

Los datos viven en **listas de objetos en memoria**, accedidas únicamente a través del patrón
**Repository**. Para probar desde esta página: use `POST /api/auth/login` y luego el botón *Authorize*.
"""


async def _ciclo_recordatorios(c: Contenedor) -> None:
    """Envía periódicamente los recordatorios vencidos (simulados)."""
    while True:
        await asyncio.sleep(c.config.intervalo_recordatorios_seg)
        try:
            await asyncio.to_thread(
                c.notificaciones.procesar_pendientes, ahora_local(c.config.zona_horaria)
            )
        except Exception:  # noqa: BLE001 - el ciclo no debe morir por un fallo puntual
            registro.exception("Error al procesar recordatorios")


def crear_app(config: Optional[Configuracion] = None) -> FastAPI:
    config = config or cargar_configuracion()
    contenedor = crear_contenedor(config)
    if config.sembrar_datos_demo:
        sembrar_datos_demo(contenedor)

    @asynccontextmanager
    async def ciclo_de_vida(_: FastAPI):
        tarea = None
        if config.recordatorios_automaticos:
            tarea = asyncio.create_task(_ciclo_recordatorios(contenedor))
        yield
        if tarea is not None:
            tarea.cancel()

    app = FastAPI(
        title="Consultorio Médico Salud Integral",
        version="1.0.0",
        description=DESCRIPCION,
        lifespan=ciclo_de_vida,
    )
    app.state.contenedor = contenedor
    registrar_manejadores(app)

    @app.middleware("http")
    async def sin_cache_en_api(request: Request, call_next):
        """Los datos clínicos no deben quedar guardados en cachés del navegador ni de proxies."""
        respuesta = await call_next(request)
        if request.url.path.startswith("/api/"):
            respuesta.headers["Cache-Control"] = "no-store"
        return respuesta

    for router in (
        salud.router,
        auth.router,
        pacientes.router,
        medicos.router,
        citas.router,
        consultas.router,
        usuarios.router,
        auditoria.router,
        recordatorios.router,
    ):
        app.include_router(router)

    # La interfaz web (JavaScript) se sirve desde el mismo servidor.
    carpeta_frontend = Path(os.getenv("FRONTEND_DIR") or Path(__file__).resolve().parents[2] / "frontend")
    if carpeta_frontend.is_dir():
        app.mount("/", StaticFiles(directory=carpeta_frontend, html=True), name="frontend")

    return app
