from fastapi import APIRouter, Depends

from app.api.deps import contenedor, requiere_roles
from app.api.schemas import (
    ProcedimientoCatalogoIn,
    ProcedimientoCatalogoOut,
    ProcedimientoCatalogoUpdate,
)
from app.container import Contenedor
from app.domain.modelos import Rol, Usuario

router = APIRouter(prefix="/api/procedimientos", tags=["Catálogo de procedimientos"])


@router.get(
    "",
    response_model=list[ProcedimientoCatalogoOut],
    summary="Catálogo de procedimientos y tarifas vigentes",
)
def listar_catalogo(
    c: Contenedor = Depends(contenedor),
    _: Usuario = Depends(requiere_roles(Rol.RECEPCION, Rol.MEDICO, Rol.ADMINISTRADOR)),
) -> list[ProcedimientoCatalogoOut]:
    return [ProcedimientoCatalogoOut.model_validate(p) for p in c.catalogo.listar()]


@router.post(
    "",
    response_model=ProcedimientoCatalogoOut,
    status_code=201,
    summary="Agregar un procedimiento al catálogo",
)
def crear_procedimiento(
    datos: ProcedimientoCatalogoIn,
    c: Contenedor = Depends(contenedor),
    _: Usuario = Depends(requiere_roles(Rol.ADMINISTRADOR)),
) -> ProcedimientoCatalogoOut:
    return ProcedimientoCatalogoOut.model_validate(c.catalogo.crear(**datos.model_dump()))


@router.put(
    "/{procedimiento_id}",
    response_model=ProcedimientoCatalogoOut,
    summary="Cambiar nombre o tarifa (lo ya realizado conserva su valor)",
)
def actualizar_procedimiento(
    procedimiento_id: int,
    datos: ProcedimientoCatalogoUpdate,
    c: Contenedor = Depends(contenedor),
    _: Usuario = Depends(requiere_roles(Rol.ADMINISTRADOR)),
) -> ProcedimientoCatalogoOut:
    cambios = datos.model_dump(exclude_unset=True)
    return ProcedimientoCatalogoOut.model_validate(c.catalogo.actualizar(procedimiento_id, **cambios))


@router.post("/{procedimiento_id}/desactivar", status_code=204, summary="Retirar del catálogo")
def desactivar_procedimiento(
    procedimiento_id: int,
    c: Contenedor = Depends(contenedor),
    _: Usuario = Depends(requiere_roles(Rol.ADMINISTRADOR)),
) -> None:
    c.catalogo.desactivar(procedimiento_id)
