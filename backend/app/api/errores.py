"""Traducción de errores de dominio y de validación a respuestas HTTP."""
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.domain.excepciones import (
    AutenticacionFallida,
    Conflicto,
    Duplicado,
    ErrorDominio,
    NoEncontrado,
    Prohibido,
    ReglaNegocio,
)

_CODIGOS = {
    NoEncontrado: 404,
    Duplicado: 409,
    Conflicto: 409,
    ReglaNegocio: 422,
    AutenticacionFallida: 401,
    Prohibido: 403,
}


def registrar_manejadores(app: FastAPI) -> None:
    @app.exception_handler(ErrorDominio)
    async def _error_dominio(_: Request, error: ErrorDominio) -> JSONResponse:
        codigo = _CODIGOS.get(type(error), 400)
        cabeceras = {"WWW-Authenticate": "Bearer"} if codigo == 401 else None
        return JSONResponse(
            status_code=codigo,
            content={"detail": error.mensaje, **error.detalle},
            headers=cabeceras,
        )

    @app.exception_handler(RequestValidationError)
    async def _error_validacion(_: Request, error: RequestValidationError) -> JSONResponse:
        mensajes = []
        for e in error.errors():
            campo = ".".join(str(parte) for parte in e["loc"] if parte not in ("body", "query", "path"))
            mensajes.append(f"{campo}: {e['msg']}" if campo else e["msg"])
        return JSONResponse(
            status_code=422,
            content={"detail": "Datos no válidos. " + "; ".join(mensajes)},
        )
