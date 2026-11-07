from typing import Optional

from fastapi import APIRouter, Depends

from app.api.deps import contenedor, requiere_roles
from app.api.mapeos import facturas_out
from app.api.schemas import (
    AnulacionIn,
    FacturaIn,
    FacturaOut,
    GlosaIn,
    PagoIn,
    PagoPagadorIn,
    RadicacionIn,
    RespuestaGlosaIn,
    ResolucionGlosaIn,
)
from app.container import Contenedor
from app.domain.modelos import EstadoFactura, Rol, Usuario

router = APIRouter(prefix="/api/facturas", tags=["Facturación"])

_recepcion = requiere_roles(Rol.RECEPCION)
_lectura = requiere_roles(Rol.RECEPCION, Rol.ADMINISTRADOR)
_cartera = requiere_roles(Rol.RECEPCION, Rol.ADMINISTRADOR)


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


@router.post("/{factura_id}/pagar", response_model=FacturaOut, summary="Registrar el pago del paciente")
def pagar(
    factura_id: int, datos: PagoIn, c: Contenedor = Depends(contenedor), usuario: Usuario = Depends(_recepcion)
) -> FacturaOut:
    """Cobra al paciente lo que le corresponde: todo si es particular, el copago si hay convenio."""
    return facturas_out(c, [c.facturacion.pagar(factura_id, datos.metodo_pago, usuario)])[0]


@router.post("/{factura_id}/anular", response_model=FacturaOut, summary="Anular una factura emitida")
def anular(
    factura_id: int, datos: AnulacionIn, c: Contenedor = Depends(contenedor), usuario: Usuario = Depends(_recepcion)
) -> FacturaOut:
    """Sin factura electrónica aceptada se anula directo; con ella, se emite primero la nota crédito (RN-23)."""
    if c.electronica.tiene_factura_aceptada(factura_id):
        return facturas_out(c, [c.electronica.anular_con_nota_credito(factura_id, datos.motivo, usuario)])[0]
    return facturas_out(c, [c.facturacion.anular(factura_id, datos.motivo)])[0]


# ---------------------------------------------------------------- cartera: radicación, abonos y glosas


@router.post("/{factura_id}/radicar", response_model=FacturaOut, summary="Radicar la factura al pagador")
def radicar(
    factura_id: int,
    datos: RadicacionIn,
    c: Contenedor = Depends(contenedor),
    _: Usuario = Depends(_cartera),
) -> FacturaOut:
    return facturas_out(c, [c.cartera.radicar(factura_id, datos.numero_radicacion)])[0]


@router.post("/{factura_id}/pagos-pagador", response_model=FacturaOut, summary="Registrar un abono del pagador")
def pago_del_pagador(
    factura_id: int,
    datos: PagoPagadorIn,
    c: Contenedor = Depends(contenedor),
    usuario: Usuario = Depends(_cartera),
) -> FacturaOut:
    factura = c.cartera.registrar_pago_pagador(
        factura_id, datos.valor, usuario, datos.metodo_pago, datos.referencia
    )
    return facturas_out(c, [factura])[0]


@router.post("/{factura_id}/glosas", response_model=FacturaOut, status_code=201, summary="Registrar una glosa del pagador")
def registrar_glosa(
    factura_id: int,
    datos: GlosaIn,
    c: Contenedor = Depends(contenedor),
    _: Usuario = Depends(_cartera),
) -> FacturaOut:
    return facturas_out(c, [c.cartera.registrar_glosa(factura_id, datos.concepto, datos.motivo, datos.valor)])[0]


@router.post("/{factura_id}/glosas/{glosa_id}/responder", response_model=FacturaOut, summary="Responder una glosa")
def responder_glosa(
    factura_id: int,
    glosa_id: int,
    datos: RespuestaGlosaIn,
    c: Contenedor = Depends(contenedor),
    _: Usuario = Depends(_cartera),
) -> FacturaOut:
    return facturas_out(c, [c.cartera.responder_glosa(factura_id, glosa_id, datos.respuesta)])[0]


@router.post("/{factura_id}/glosas/{glosa_id}/resolver", response_model=FacturaOut, summary="Cerrar una glosa: aceptada o levantada")
def resolver_glosa(
    factura_id: int,
    glosa_id: int,
    datos: ResolucionGlosaIn,
    c: Contenedor = Depends(contenedor),
    _: Usuario = Depends(_cartera),
) -> FacturaOut:
    return facturas_out(c, [c.cartera.resolver_glosa(factura_id, glosa_id, datos.aceptada, datos.nota)])[0]
