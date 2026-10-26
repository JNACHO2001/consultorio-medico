from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.api.deps import contenedor, requiere_roles
from app.api.schemas import AuditoriaOut
from app.container import Contenedor
from app.domain.modelos import Rol, Usuario

router = APIRouter(prefix="/api/auditoria", tags=["Auditoría"])


@router.get("", response_model=list[AuditoriaOut], summary="Consultar bitácora de auditoría (CU-12)")
def consultar_bitacora(
    usuario: Optional[str] = Query(None, max_length=60),
    entidad: Optional[str] = Query(None, max_length=40),
    accion: Optional[str] = Query(None, max_length=40),
    limite: int = Query(200, ge=1, le=1000),
    c: Contenedor = Depends(contenedor),
    _: Usuario = Depends(requiere_roles(Rol.ADMINISTRADOR)),
) -> list[AuditoriaOut]:
    registros = c.auditoria.consultar(usuario, entidad, accion, limite)
    return [AuditoriaOut.model_validate(r) for r in registros]
