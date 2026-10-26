"""Dependencias de FastAPI: acceso al contenedor y control de acceso por rol (RNF-01)."""
from dataclasses import dataclass
from typing import Optional

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.container import Contenedor
from app.core.contexto import UsuarioContexto, establecer_usuario
from app.domain.excepciones import AutenticacionFallida, Prohibido
from app.domain.modelos import Rol, Usuario

_esquema_bearer = HTTPBearer(auto_error=False, description="Token obtenido en /api/auth/login")


@dataclass
class Sesion:
    usuario: Usuario
    jti: str


def contenedor(request: Request) -> Contenedor:
    return request.app.state.contenedor


# Es `async` a propósito: así el usuario queda en el contexto de la petición y los
# repositorios pueden anotarlo en la bitácora (ver app/core/contexto.py).
async def sesion_actual(
    credenciales: Optional[HTTPAuthorizationCredentials] = Depends(_esquema_bearer),
    c: Contenedor = Depends(contenedor),
) -> Sesion:
    if credenciales is None:
        raise AutenticacionFallida("Debe iniciar sesión.")
    usuario, datos = c.autenticacion.autenticar_token(credenciales.credentials)
    establecer_usuario(UsuarioContexto(usuario.id, usuario.nombre_usuario, usuario.rol))
    return Sesion(usuario=usuario, jti=datos["jti"])


def requiere_roles(*roles: Rol):
    """Permite el acceso solo a los roles indicados y devuelve el usuario autenticado."""

    async def dependencia(sesion: Sesion = Depends(sesion_actual)) -> Usuario:
        if sesion.usuario.rol not in roles:
            raise Prohibido("Su rol no tiene permiso para esta operación.")
        return sesion.usuario

    return dependencia
