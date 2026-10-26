from typing import Optional

from fastapi import APIRouter, Depends

from app.api.deps import contenedor, requiere_roles
from app.api.mapeos import facturas_out
from app.api.schemas import AnulacionIn, FacturaIn, FacturaOut, PagoIn
from app.container import Contenedor
from app.domain.modelos import EstadoFactura, Rol, Usuario

router = APIRouter(prefix="/api/facturas", tags=["Facturación"])

_recepcion = requiere_roles(Rol.RECEPCION)
_lectura = requiere_roles(Rol.RECEPCION, Rol.ADMINISTRADOR)


@router.post("", response_model=FacturaOut, status_code=201, summary="Facturar procedimientos de un ingreso")
def facturar(
    datos: FacturaIn, c: Contenedor = Depends(contenedor), usuario: Usuario = Depends(_recepcion)
) -> FacturaOut:
    factura = c.facturacion.facturar(datos.ingreso_id, usuario, datos.procedimiento_ids)
    return facturas_out(c, [factura])[0]


@router.get("", response_model=list[FacturaOut], summary="Listar facturas")
def listar(
    estado: Optional[EstadoFactura] = None,
    paciente_id: Optional[int] = None,
    ingreso_id: Optional[int] = None,
    c: Contenedor = Depends(contenedor),
    _: Usuario = Depends(_lectura),
) -> list[FacturaOut]:
    return facturas_out(c, c.facturacion.buscar(estado, paciente_id, ingreso_id))


@router.get("/{factura_id}", response_model=FacturaOut, summary="Ver una factura")
def ver(factura_id: int, c: Contenedor = Depends(contenedor), _: Usuario = Depends(_lectura)) -> FacturaOut:
    return facturas_out(c, [c.facturacion.obtener(factura_id)])[0]


@router.post("/{factura_id}/pagar", response_model=FacturaOut, summary="Registrar el pago")
def pagar(
    factura_id: int, datos: PagoIn, c: Contenedor = Depends(contenedor), _: Usuario = Depends(_recepcion)
) -> FacturaOut:
    return facturas_out(c, [c.facturacion.pagar(factura_id, datos.metodo_pago)])[0]


@router.post("/{factura_id}/anular", response_model=FacturaOut, summary="Anular una factura emitida")
def anular(
    factura_id: int, datos: AnulacionIn, c: Contenedor = Depends(contenedor), _: Usuario = Depends(_recepcion)
) -> FacturaOut:
    return facturas_out(c, [c.facturacion.anular(factura_id, datos.motivo)])[0]
