from fastapi import APIRouter, Depends

from app.api.deps import contenedor, requiere_roles
from app.api.schemas import (
    ConvenioIn,
    ConvenioOut,
    ConvenioUpdate,
    PagadorIn,
    PagadorOut,
    PagadorUpdate,
)
from app.container import Contenedor
from app.domain.modelos import Pagador, Rol, Usuario

router = APIRouter(prefix="/api", tags=["Pagadores y convenios"])

_lectura = requiere_roles(Rol.RECEPCION, Rol.ADMINISTRADOR)
_admin = requiere_roles(Rol.ADMINISTRADOR)


def _pagador_out(c: Contenedor, pagador: Pagador) -> PagadorOut:
    salida = PagadorOut.model_validate(pagador)
    salida.convenios = [ConvenioOut.model_validate(v) for v in c.convenios.listar_convenios(pagador.id)]
    return salida


@router.get("/pagadores", response_model=list[PagadorOut], summary="Pagadores con sus convenios vigentes")
def listar_pagadores(c: Contenedor = Depends(contenedor), _: Usuario = Depends(_lectura)) -> list[PagadorOut]:
    return [_pagador_out(c, p) for p in c.convenios.listar_pagadores()]


@router.post("/pagadores", response_model=PagadorOut, status_code=201, summary="Crear un pagador (EPS, ARL, SOAT…)")
def crear_pagador(datos: PagadorIn, c: Contenedor = Depends(contenedor), _: Usuario = Depends(_admin)) -> PagadorOut:
    return _pagador_out(c, c.convenios.crear_pagador(datos.codigo, datos.nombre, datos.tipo, datos.nit))


@router.put("/pagadores/{pagador_id}", response_model=PagadorOut, summary="Cambiar nombre o NIT del pagador")
def actualizar_pagador(
    pagador_id: int, datos: PagadorUpdate, c: Contenedor = Depends(contenedor), _: Usuario = Depends(_admin)
) -> PagadorOut:
    return _pagador_out(c, c.convenios.actualizar_pagador(pagador_id, **datos.model_dump(exclude_unset=True)))


@router.post("/pagadores/{pagador_id}/desactivar", status_code=204, summary="Retirar un pagador")
def desactivar_pagador(pagador_id: int, c: Contenedor = Depends(contenedor), _: Usuario = Depends(_admin)) -> None:
    c.convenios.desactivar_pagador(pagador_id)


@router.post(
    "/pagadores/{pagador_id}/convenios", response_model=ConvenioOut, status_code=201, summary="Crear un convenio"
)
def crear_convenio(
    pagador_id: int, datos: ConvenioIn, c: Contenedor = Depends(contenedor), _: Usuario = Depends(_admin)
) -> ConvenioOut:
    return ConvenioOut.model_validate(c.convenios.crear_convenio(pagador_id, **datos.model_dump()))


@router.put("/convenios/{convenio_id}", response_model=ConvenioOut, summary="Cambiar las condiciones de un convenio")
def actualizar_convenio(
    convenio_id: int, datos: ConvenioUpdate, c: Contenedor = Depends(contenedor), _: Usuario = Depends(_admin)
) -> ConvenioOut:
    return ConvenioOut.model_validate(
        c.convenios.actualizar_convenio(convenio_id, **datos.model_dump(exclude_unset=True))
    )


@router.post("/convenios/{convenio_id}/desactivar", status_code=204, summary="Retirar un convenio")
def desactivar_convenio(convenio_id: int, c: Contenedor = Depends(contenedor), _: Usuario = Depends(_admin)) -> None:
    c.convenios.desactivar_convenio(convenio_id)
