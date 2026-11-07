from datetime import date
from typing import Any, Optional

from fastapi import APIRouter, Depends

from app.api.deps import contenedor, requiere_roles
from app.container import Contenedor
from app.domain.modelos import Rol, Usuario

router = APIRouter(prefix="/api/rips", tags=["RIPS"])


@router.get("", summary="Borrador del RIPS del periodo, con las inconsistencias por corregir")
def generar(
    desde: date,
    hasta: date,
    pagador_id: Optional[int] = None,
    c: Contenedor = Depends(contenedor),
    _: Usuario = Depends(requiere_roles(Rol.ADMINISTRADOR)),
) -> dict[str, Any]:
    return c.rips.generar(desde, hasta, pagador_id)
