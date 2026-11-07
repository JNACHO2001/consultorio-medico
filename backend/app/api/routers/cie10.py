from fastapi import APIRouter, Depends, Query

from app.api.deps import contenedor, requiere_roles
from app.api.schemas import Cie10Out
from app.container import Contenedor
from app.domain.modelos import Rol, Usuario

router = APIRouter(prefix="/api/cie10", tags=["Catálogo CIE-10"])


@router.get("", response_model=list[Cie10Out], summary="Buscar diagnósticos CIE-10 por código o por texto")
def buscar(
    q: str = Query("", max_length=80),
    c: Contenedor = Depends(contenedor),
    _: Usuario = Depends(requiere_roles(Rol.MEDICO, Rol.ADMINISTRADOR)),
) -> list[Cie10Out]:
    return [Cie10Out(codigo=codigo, descripcion=d) for codigo, d in c.cie10.buscar(q)]
