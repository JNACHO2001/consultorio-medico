"""Inicio y cierre de sesión (CU-01, RF-12)."""
from __future__ import annotations

import threading

from app.config import Configuracion
from app.core.auditoria import auditar, auditar_como
from app.core.seguridad import (
    crear_token,
    decodificar_token,
    hash_contrasena,
    verificar_contrasena,
)
from app.domain.excepciones import AutenticacionFallida
from app.domain.modelos import Usuario
from app.repositories.interfaces import IAuditoriaRepository, IUsuarioRepository


class AutenticacionService:
    def __init__(
        self,
        usuarios: IUsuarioRepository,
        auditoria: IAuditoriaRepository,
        config: Configuracion,
    ) -> None:
        self._usuarios = usuarios
        self._auditoria = auditoria
        self._config = config
        self._revocados: set[str] = set()
        self._lock = threading.Lock()
        # Hash de relleno: igualar el tiempo de respuesta cuando el usuario no existe.
        self._hash_relleno = hash_contrasena("relleno", config.iteraciones_hash)

    def iniciar_sesion(self, nombre_usuario: str, contrasena: str) -> tuple[str, Usuario]:
        usuario = self._usuarios.obtener_por_nombre_usuario(nombre_usuario or "")
        hash_a_verificar = usuario.contrasena_hash if usuario else self._hash_relleno
        correcta = verificar_contrasena(contrasena or "", hash_a_verificar)
        if usuario is None or not correcta:
            auditar_como(
                self._auditoria, 0, (nombre_usuario or "")[:60], "Sesion", "INICIO_SESION_FALLIDO"
            )
            raise AutenticacionFallida("Usuario o contraseña incorrectos.")
        token, _ = crear_token(usuario.id, self._config.secret_key, self._config.token_minutos)
        auditar_como(
            self._auditoria, usuario.id, usuario.nombre_usuario, "Sesion", "INICIO_SESION", usuario.id
        )
        return token, usuario

    def autenticar_token(self, token: str) -> tuple[Usuario, dict]:
        """Valida el token y devuelve el usuario y los datos del token."""
        datos = decodificar_token(token, self._config.secret_key)
        with self._lock:
            if datos.get("jti") in self._revocados:
                raise AutenticacionFallida("La sesión fue cerrada. Inicie sesión de nuevo.")
        usuario = self._usuarios.obtener_por_id(int(datos["sub"]))
        if usuario is None:
            raise AutenticacionFallida("El usuario ya no está activo.")
        return usuario, datos

    def cerrar_sesion(self, jti: str, usuario: Usuario) -> None:
        with self._lock:
            self._revocados.add(jti)
        auditar(self._auditoria, "Sesion", "CIERRE_SESION", usuario.id)
