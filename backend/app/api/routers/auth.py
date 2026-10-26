from fastapi import APIRouter, Depends, Response

from app.api.deps import Sesion, contenedor, sesion_actual
from app.api.schemas import LoginIn, LoginOut, UsuarioOut
from app.container import Contenedor

router = APIRouter(prefix="/api/auth", tags=["Sesión"])


@router.post("/login", response_model=LoginOut, summary="Iniciar sesión (CU-01)")
def iniciar_sesion(datos: LoginIn, c: Contenedor = Depends(contenedor)) -> LoginOut:
    token, usuario = c.autenticacion.iniciar_sesion(datos.usuario, datos.contrasena)
    return LoginOut(
        access_token=token,
        expira_en_minutos=c.config.token_minutos,
        usuario=UsuarioOut.model_validate(usuario),
    )


@router.get("/me", response_model=UsuarioOut, summary="Usuario de la sesión actual")
async def usuario_actual(sesion: Sesion = Depends(sesion_actual)) -> UsuarioOut:
    return UsuarioOut.model_validate(sesion.usuario)


@router.post("/logout", status_code=204, summary="Cerrar sesión")
def cerrar_sesion(
    sesion: Sesion = Depends(sesion_actual), c: Contenedor = Depends(contenedor)
) -> Response:
    c.autenticacion.cerrar_sesion(sesion.jti, sesion.usuario)
    return Response(status_code=204)
