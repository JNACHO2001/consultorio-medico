"""Contraseñas cifradas (hash) y tokens de sesión (RNF-02, RF-12)."""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import uuid
from datetime import datetime, timedelta, timezone

import jwt

from app.domain.excepciones import AutenticacionFallida

_ALGORITMO = "HS256"


def _b64(datos: bytes) -> str:
    return base64.b64encode(datos).decode("ascii")


def hash_contrasena(contrasena: str, iteraciones: int = 200_000) -> str:
    """PBKDF2-HMAC-SHA256 con sal aleatoria. Nunca se guarda la contraseña en texto plano."""
    sal = os.urandom(16)
    resumen = hashlib.pbkdf2_hmac("sha256", contrasena.encode("utf-8"), sal, iteraciones)
    return f"pbkdf2_sha256${iteraciones}${_b64(sal)}${_b64(resumen)}"


def verificar_contrasena(contrasena: str, almacenado: str) -> bool:
    try:
        _, iteraciones, sal, esperado = almacenado.split("$")
        resumen = hashlib.pbkdf2_hmac(
            "sha256",
            contrasena.encode("utf-8"),
            base64.b64decode(sal),
            int(iteraciones),
        )
        return hmac.compare_digest(_b64(resumen), esperado)
    except (ValueError, TypeError):
        return False


def crear_token(usuario_id: int, secreto: str, minutos: int) -> tuple[str, str]:
    """Devuelve (token, jti). El token expira a los `minutos` (cierre por inactividad)."""
    jti = uuid.uuid4().hex
    ahora = datetime.now(timezone.utc)
    carga = {
        "sub": str(usuario_id),
        "jti": jti,
        "iat": ahora,
        "exp": ahora + timedelta(minutes=minutos),
    }
    return jwt.encode(carga, secreto, algorithm=_ALGORITMO), jti


def decodificar_token(token: str, secreto: str) -> dict:
    try:
        return jwt.decode(token, secreto, algorithms=[_ALGORITMO])
    except jwt.ExpiredSignatureError:
        raise AutenticacionFallida("La sesión expiró. Inicie sesión de nuevo.")
    except jwt.InvalidTokenError:
        raise AutenticacionFallida("Sesión no válida.")
