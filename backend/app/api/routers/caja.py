from typing import Optional

from fastapi import APIRouter, Depends

from app.api.deps import contenedor, requiere_roles
from app.api.mapeos import cajas_out
from app.api.schemas import AperturaCajaIn, CajaDetalleOut, CajaOut, CierreCajaIn
from app.container import Contenedor
from app.domain.modelos import Rol, Usuario

router = APIRouter(prefix="/api/caja", tags=["Caja"])

_cajero = requiere_roles(Rol.RECEPCION)
_lectura = requiere_roles(Rol.RECEPCION, Rol.ADMINISTRADOR)


@router.get("/actual", response_model=Optional[CajaDetalleOut], summary="Mi caja abierta (o nada)")
def actual(c: Contenedor = Depends(contenedor), usuario: Usuario = Depends(_cajero)):
    caja = c.cajas.actual(usuario)
    return cajas_out(c, [caja], con_recibos=True)[0] if caja else None


@router.get("", response_model=list[CajaOut], summary="Turnos de caja")
def listar(c: Contenedor = Depends(contenedor), usuario: Usuario = Depends(_lectura)) -> list[CajaOut]:
    return cajas_out(c, c.cajas.listar(usuario))


@router.get("/{caja_id}", response_model=CajaDetalleOut, summary="Ver un turno con sus recibos")
def ver(caja_id: int, c: Contenedor = Depends(contenedor), usuario: Usuario = Depends(_lectura)) -> CajaDetalleOut:
    return cajas_out(c, [c.cajas.ver(caja_id, usuario)], con_recibos=True)[0]


@router.post("/apertura", response_model=CajaDetalleOut, status_code=201, summary="Abrir caja")
def abrir(datos: AperturaCajaIn, c: Contenedor = Depends(contenedor), usuario: Usuario = Depends(_cajero)) -> CajaDetalleOut:
    return cajas_out(c, [c.cajas.abrir(usuario, datos.base_inicial)], con_recibos=True)[0]


@router.post("/{caja_id}/cierre", response_model=CajaDetalleOut, summary="Cerrar caja contando el efectivo")
def cerrar(
    caja_id: int, datos: CierreCajaIn, c: Contenedor = Depends(contenedor), usuario: Usuario = Depends(_cajero)
) -> CajaDetalleOut:
    cerrada = c.cajas.cerrar(caja_id, usuario, datos.efectivo_contado, datos.observaciones)
    return cajas_out(c, [cerrada], con_recibos=True)[0]
