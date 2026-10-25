"""Excepciones de dominio.

Los servicios las lanzan; la capa API las traduce a códigos HTTP
(ver app/api/errores.py). Así la lógica de negocio no depende de HTTP.
"""
from __future__ import annotations

from typing import Any, Optional


class ErrorDominio(Exception):
    """Base de los errores de negocio."""

    def __init__(self, mensaje: str, detalle: Optional[dict[str, Any]] = None) -> None:
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.detalle = detalle or {}


class NoEncontrado(ErrorDominio):
    """El recurso solicitado no existe."""


class Duplicado(ErrorDominio):
    """Se intentó crear un registro que ya existe (RN-01)."""


class Conflicto(ErrorDominio):
    """La operación choca con el estado actual (por ejemplo, cruce de horarios, RN-02)."""


class ReglaNegocio(ErrorDominio):
    """La operación viola una regla de negocio o los datos no son válidos."""


class AutenticacionFallida(ErrorDominio):
    """Credenciales inválidas o sesión no válida."""


class Prohibido(ErrorDominio):
    """El usuario no tiene permiso para la operación (RNF-01)."""
