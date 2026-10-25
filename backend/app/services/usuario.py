"""Gestión de usuarios y roles (CU-11, RF-11)."""
from __future__ import annotations

import re
import threading

from app.config import Configuracion
from app.core.auditoria import auditar
from app.core.seguridad import hash_contrasena
from app.domain.excepciones import Duplicado, NoEncontrado, ReglaNegocio
from app.domain.modelos import Medico, Rol, Usuario
from app.repositories.interfaces import IAuditoriaRepository, IUsuarioRepository

_PATRON_USUARIO = re.compile(r"^[a-z0-9._-]{3,30}$")


class UsuarioService:
    def __init__(
        self,
        usuarios: IUsuarioRepository,
        auditoria: IAuditoriaRepository,
        config: Configuracion,
    ) -> None:
        self._usuarios = usuarios
        self._auditoria = auditoria
        self._config = config
        self._lock = threading.Lock()

    def crear_usuario(
        self,
        nombre_usuario: str,
        contrasena: str,
        nombre_completo: str,
        rol: Rol,
        especialidad: str = "",
        registro_medico: str = "",
    ) -> Usuario:
        nombre_usuario = (nombre_usuario or "").strip().lower()
        nombre_completo = (nombre_completo or "").strip()
        if not _PATRON_USUARIO.match(nombre_usuario):
            raise ReglaNegocio(
                "El usuario debe tener entre 3 y 30 caracteres: letras minúsculas, números, punto, guion o guion bajo."
            )
        if not nombre_completo:
            raise ReglaNegocio("El nombre completo es obligatorio.")
        self._validar_contrasena(contrasena)

        with self._lock:
            if self._usuarios.obtener_por_nombre_usuario(nombre_usuario, incluir_inactivos=True):
                raise Duplicado("Ya existe un usuario con ese nombre de usuario.")
            hash_ = hash_contrasena(contrasena, self._config.iteraciones_hash)
            if rol == Rol.MEDICO:
                nuevo: Usuario = Medico(
                    nombre_usuario=nombre_usuario,
                    contrasena_hash=hash_,
                    nombre_completo=nombre_completo,
                    especialidad=(especialidad or "Medicina general").strip(),
                    registro_medico=(registro_medico or "").strip(),
                )
            else:
                nuevo = Usuario(
                    nombre_usuario=nombre_usuario,
                    contrasena_hash=hash_,
                    nombre_completo=nombre_completo,
                    rol=rol,
                )
            creado = self._usuarios.agregar(nuevo)
        auditar(self._auditoria, "Usuario", "CREACION", creado.id)
        return creado

    def listar_usuarios(self, incluir_inactivos: bool = True) -> list[Usuario]:
        return self._usuarios.listar(incluir_inactivos=incluir_inactivos)

    def listar_medicos(self) -> list[Usuario]:
        medicos = [u for u in self._usuarios.listar() if u.rol == Rol.MEDICO]
        return sorted(medicos, key=lambda m: m.nombre_completo)

    def desactivar_usuario(self, usuario_id: int, actor: Usuario) -> None:
        if usuario_id == actor.id:
            raise ReglaNegocio("No puede desactivar su propio usuario.")
        if self._usuarios.obtener_por_id(usuario_id) is None:
            raise NoEncontrado("El usuario no existe o ya está inactivo.")
        self._usuarios.desactivar(usuario_id)
        auditar(self._auditoria, "Usuario", "DESACTIVACION", usuario_id)

    @staticmethod
    def _validar_contrasena(contrasena: str) -> None:
        contrasena = contrasena or ""
        if len(contrasena) < 8 or not re.search(r"[A-Za-z]", contrasena) or not re.search(r"\d", contrasena):
            raise ReglaNegocio("La contraseña debe tener al menos 8 caracteres, con letras y números.")
