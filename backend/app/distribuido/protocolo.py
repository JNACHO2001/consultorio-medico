"""Protocolo entre el proxy y los nodos proveedor: un mensaje JSON por línea (UTF-8) sobre TCP.

Solicitudes::

    {"id": 1, "tipo": "ENVIAR", "clave": "FACTURA:SETP990000000:<cufe>", "documento": {...}}
    {"id": 2, "tipo": "PING"}
    {"id": 3, "tipo": "ESTADO"}

Respuestas (repiten el ``id`` y dicen qué nodo respondió)::

    {"id": 1, "ok": true, "aceptado": true, "codigo": "SIM-00", "mensaje": "...", "nodo": "nodo-1", "ms": 41.2}
    {"id": 1, "ok": false, "error": "OCUPADO" | "ERROR_NODO" | "SOLICITUD_INVALIDA", "nodo": "nodo-1"}

``clave`` es la clave de idempotencia: el nodo no repite el trabajo de una clave que ya procesó,
de modo que reintentar una solicitud (por ejemplo tras un tiempo de espera agotado) es seguro.
"""
from __future__ import annotations

import json
import socket
from datetime import datetime
from typing import Any

from app.domain.modelos import DocumentoElectronico, TipoDocumentoElectronico

MAX_LINEA = 1_000_000  # bytes: un documento con su XML pesa unos pocos KB

# Campos del documento que viajan al nodo (el resto es estado local del consultorio).
_CAMPOS = (
    "factura_id", "prefijo", "consecutivo", "adquirente_tipo_documento", "adquirente_documento",
    "adquirente_dv", "adquirente_nombre", "adquirente_es_pagador", "valor_bruto", "valor", "cufe", "xml",
)


class ErrorProtocolo(Exception):
    """El otro extremo cerró la conexión o envió algo que no es un mensaje válido."""


def clave_idempotencia(doc: DocumentoElectronico) -> str:
    return f"{doc.tipo.value}:{doc.numero}:{doc.cufe}"


def documento_a_dict(doc: DocumentoElectronico) -> dict[str, Any]:
    datos: dict[str, Any] = {campo: getattr(doc, campo) for campo in _CAMPOS}
    datos["tipo"] = doc.tipo.value
    datos["fecha"] = doc.fecha.isoformat() if doc.fecha else None
    return datos


def dict_a_documento(datos: dict[str, Any]) -> DocumentoElectronico:
    valores = {campo: datos[campo] for campo in _CAMPOS if campo in datos}
    fecha = datos.get("fecha")
    return DocumentoElectronico(
        tipo=TipoDocumentoElectronico(datos["tipo"]),
        fecha=datetime.fromisoformat(fecha) if fecha else None,
        **valores,
    )


def codificar(mensaje: dict[str, Any]) -> bytes:
    return (json.dumps(mensaje, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")


def enviar_mensaje(conexion: socket.socket, mensaje: dict[str, Any]) -> None:
    conexion.sendall(codificar(mensaje))


def decodificar(linea: bytes) -> dict[str, Any]:
    try:
        mensaje = json.loads(linea)
    except ValueError as error:
        raise ErrorProtocolo("Mensaje que no es JSON.") from error
    if not isinstance(mensaje, dict):
        raise ErrorProtocolo("El mensaje debe ser un objeto JSON.")
    return mensaje
