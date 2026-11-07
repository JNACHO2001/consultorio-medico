from fastapi import APIRouter, Depends

from app.api.mapeos import facturas_out
from app.api.deps import contenedor, requiere_roles
from app.api.schemas import CarteraDetalleOut, CarteraPagadorOut, TramosCarteraOut
from app.container import Contenedor
from app.domain.modelos import Rol, Usuario
from app.services.cartera import ResumenCartera

router = APIRouter(prefix="/api/cartera", tags=["Cartera de pagadores"])

_lectura = requiere_roles(Rol.RECEPCION, Rol.ADMINISTRADOR)


def _resumen_out(r: ResumenCartera) -> CarteraPagadorOut:
    return CarteraPagadorOut(
        pagador_id=r.pagador_id,
        pagador_nombre=r.pagador_nombre,
        n_facturas=r.n_facturas,
        facturado=r.facturado,
        recaudado=r.recaudado,
        glosa_aceptada=r.glosa_aceptada,
        en_disputa=r.en_disputa,
        saldo=r.saldo,
        tramos=TramosCarteraOut(**r.tramos),
    )


@router.get("", response_model=list[CarteraPagadorOut], summary="Cartera por pagador con su antigüedad")
def resumen(c: Contenedor = Depends(contenedor), _: Usuario = Depends(_lectura)) -> list[CarteraPagadorOut]:
    return [_resumen_out(r) for r in c.cartera.resumen()]


@router.get("/{pagador_id}", response_model=CarteraDetalleOut, summary="Facturas de un pagador")
def detalle(
    pagador_id: int, c: Contenedor = Depends(contenedor), _: Usuario = Depends(_lectura)
) -> CarteraDetalleOut:
    c.convenios.obtener_pagador(pagador_id, incluir_inactivo=True)  # 404 si no existe
    resumen_pagador = next((r for r in c.cartera.resumen() if r.pagador_id == pagador_id), None)
    facturas = c.cartera.facturas_del_pagador(pagador_id)
    return CarteraDetalleOut(
        resumen=_resumen_out(resumen_pagador) if resumen_pagador else None,
        facturas=facturas_out(c, facturas),
    )
