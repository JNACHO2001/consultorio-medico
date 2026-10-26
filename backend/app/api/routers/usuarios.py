from fastapi import APIRouter, Depends, Response

from app.api.deps import contenedor, requiere_roles
from app.api.schemas import UsuarioIn, UsuarioOut
from app.container import Contenedor
from app.domain.modelos import Rol, Usuario

router = APIRouter(prefix="/api/usuarios", tags=["Usuarios y roles"])

_admin = requiere_roles(Rol.ADMINISTRADOR)


@router.get("", response_model=list[UsuarioOut], summary="Listar usuarios")
def listar_usuarios(c: Contenedor = Depends(contenedor), _: Usuario = Depends(_admin)) -> list[UsuarioOut]:
    return [UsuarioOut.model_validate(u) for u in c.usuarios.listar_usuarios()]


@router.post("", response_model=UsuarioOut, status_code=201, summary="Crear usuario y asignar rol (CU-11)")
def crear_usuario(
    datos: UsuarioIn, c: Contenedor = Depends(contenedor), _: Usuario = Depends(_admin)
) -> UsuarioOut:
    usuario = c.usuarios.crear_usuario(**datos.model_dump())
    return UsuarioOut.model_validate(usuario)


@router.post("/{usuario_id}/desactivar", status_code=204, summary="Desactivar usuario (borrado lógico)")
def desactivar_usuario(
    usuario_id: int, c: Contenedor = Depends(contenedor), admin: Usuario = Depends(_admin)
) -> Response:
    c.usuarios.desactivar_usuario(usuario_id, admin)
    return Response(status_code=204)
