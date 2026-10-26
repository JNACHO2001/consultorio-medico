from fastapi import APIRouter, Depends

from app.api.deps import contenedor, requiere_roles
from app.api.schemas import RecordatorioOut
from app.container import Contenedor
from app.core.tiempo import ahora_local
from app.domain.modelos import Rol, Usuario

router = APIRouter(prefix="/api/recordatorios", tags=["Recordatorios"])


@router.get("", response_model=list[RecordatorioOut], summary="Recordatorios programados y enviados")
def listar_recordatorios(
    c: Contenedor = Depends(contenedor),
    _: Usuario = Depends(requiere_roles(Rol.ADMINISTRADOR, Rol.RECEPCION)),
) -> list[RecordatorioOut]:
    return [RecordatorioOut.model_validate(r) for r in c.notificaciones.listar_recordatorios()]


@router.post(
    "/procesar",
    response_model=list[RecordatorioOut],
    summary="Enviar ahora los recordatorios cuya hora ya llegó (CU-10)",
)
def procesar_recordatorios(
    c: Contenedor = Depends(contenedor),
    _: Usuario = Depends(requiere_roles(Rol.ADMINISTRADOR)),
) -> list[RecordatorioOut]:
    enviados = c.notificaciones.procesar_pendientes(ahora_local(c.config.zona_horaria))
    return [RecordatorioOut.model_validate(r) for r in enviados]
