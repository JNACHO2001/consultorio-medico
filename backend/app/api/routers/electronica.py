from typing import Optional

from fastapi import APIRouter, Depends
from fastapi.responses import Response

from app.api.deps import contenedor, requiere_roles
from app.api.mapeos import documentos_out, facturas_out
from app.api.schemas import DocumentoElectronicoOut, FacturaOut, NotaCreditoIn
from app.container import Contenedor
from app.domain.modelos import EstadoDocumentoElectronico, Rol, TipoDocumentoElectronico, Usuario

router = APIRouter(prefix="/api/electronica", tags=["Facturación electrónica"])

_facturacion = requiere_roles(Rol.RECEPCION, Rol.ADMINISTRADOR)


@router.get("/documentos", response_model=list[DocumentoElectronicoOut], summary="Listar documentos electrónicos")
def listar(
    factura_id: Optional[int] = None,
    tipo: Optional[TipoDocumentoElectronico] = None,
    estado: Optional[EstadoDocumentoElectronico] = None,
    c: Contenedor = Depends(contenedor),
    _: Usuario = Depends(_facturacion),
) -> list[DocumentoElectronicoOut]:
    return documentos_out(c, c.electronica.buscar(factura_id, tipo, estado))


@router.get("/proveedor", summary="Proveedor tecnológico y ambiente configurados")
def proveedor(c: Contenedor = Depends(contenedor), _: Usuario = Depends(_facturacion)) -> dict:
    cfg = c.config
    return {
        "proveedor": c.electronica.proveedor,
        "ambiente": "Habilitación (pruebas)" if cfg.dian_ambiente == "2" else "Producción",
        "prefijo": cfg.dian_prefijo,
        "resolucion": cfg.dian_resolucion,
        "rango_desde": cfg.dian_rango_desde,
        "rango_hasta": cfg.dian_rango_hasta,
        "obligatoria": cfg.dian_obligatoria,
    }


@router.get("/documentos/{documento_id}", response_model=DocumentoElectronicoOut, summary="Ver un documento electrónico")
def ver(documento_id: int, c: Contenedor = Depends(contenedor), _: Usuario = Depends(_facturacion)) -> DocumentoElectronicoOut:
    return documentos_out(c, [c.electronica.obtener(documento_id)])[0]


@router.get("/documentos/{documento_id}/xml", summary="Descargar el XML del documento")
def xml(documento_id: int, c: Contenedor = Depends(contenedor), _: Usuario = Depends(_facturacion)) -> Response:
    doc = c.electronica.obtener(documento_id)
    return Response(
        content=doc.xml,
        media_type="application/xml",
        headers={"Content-Disposition": f'attachment; filename="{doc.numero}.xml"'},
    )


@router.post("/facturas/{factura_id}/emitir", response_model=DocumentoElectronicoOut, status_code=201, summary="Emitir la factura electrónica")
def emitir(
    factura_id: int, c: Contenedor = Depends(contenedor), usuario: Usuario = Depends(_facturacion)
) -> DocumentoElectronicoOut:
    return documentos_out(c, [c.electronica.emitir(factura_id, usuario)])[0]


@router.post("/documentos/{documento_id}/reintentar", response_model=DocumentoElectronicoOut, summary="Reintentar un documento rechazado")
def reintentar(
    documento_id: int, c: Contenedor = Depends(contenedor), usuario: Usuario = Depends(_facturacion)
) -> DocumentoElectronicoOut:
    return documentos_out(c, [c.electronica.reintentar(documento_id, usuario)])[0]


@router.post("/facturas/{factura_id}/notas-credito", response_model=DocumentoElectronicoOut, status_code=201, summary="Emitir una nota crédito")
def nota_credito(
    factura_id: int,
    datos: NotaCreditoIn,
    c: Contenedor = Depends(contenedor),
    usuario: Usuario = Depends(_facturacion),
) -> DocumentoElectronicoOut:
    nota = c.electronica.emitir_nota_credito(factura_id, datos.concepto, usuario, datos.motivo, datos.glosa_id)
    return documentos_out(c, [nota])[0]
