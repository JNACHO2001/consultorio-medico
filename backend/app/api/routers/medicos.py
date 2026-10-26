from fastapi import APIRouter, Depends

from app.api.deps import contenedor, requiere_roles
from app.api.schemas import MedicoOut
from app.container import Contenedor
from app.domain.modelos import Rol, Usuario

router = APIRouter(prefix="/api/medicos", tags=["Médicos"])


@router.get("", response_model=list[MedicoOut], summary="Listar médicos activos")
def listar_medicos(
    c: Contenedor = Depends(contenedor),
    _: Usuario = Depends(requiere_roles(Rol.RECEPCION, Rol.MEDICO)),
) -> list[MedicoOut]:
    return [MedicoOut.model_validate(m) for m in c.usuarios.listar_medicos()]
