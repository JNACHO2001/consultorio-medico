from typing import Optional

from fastapi import APIRouter, Depends

from app.api.deps import contenedor, requiere_roles
from app.api.mapeos import ordenes_out
from app.api.schemas import AnulacionIn, OrdenIn, OrdenOut, ResultadoIn
from app.container import Contenedor
from app.domain.modelos import AreaApoyo, EstadoOrden, ResultadoValor, Rol, Usuario

router = APIRouter(prefix="/api/ordenes", tags=["Órdenes y resultados"])

_medico = requiere_roles(Rol.MEDICO)
_clinico = requiere_roles(Rol.MEDICO, Rol.LABORATORIO)


@router.get("", response_model=list[OrdenOut], summary="Órdenes de apoyo diagnóstico con sus resultados")
def listar(
    estado: Optional[EstadoOrden] = None,
    ingreso_id: Optional[int] = None,
    paciente_id: Optional[int] = None,
    area: Optional[AreaApoyo] = None,
    c: Contenedor = Depends(contenedor),
    _: Usuario = Depends(_clinico),
) -> list[OrdenOut]:
    return ordenes_out(c, c.ordenes.buscar(estado, ingreso_id, paciente_id, area))


@router.post("", response_model=OrdenOut, status_code=201, summary="Ordenar un servicio de apoyo diagnóstico")
def crear(datos: OrdenIn, c: Contenedor = Depends(contenedor), medico: Usuario = Depends(_medico)) -> OrdenOut:
    orden = c.ordenes.crear(
        datos.ingreso_id, medico, datos.procedimiento_id, datos.cantidad, datos.prioridad, datos.indicacion
    )
    return ordenes_out(c, [orden])[0]


@router.post("/{orden_id}/anular", response_model=OrdenOut, summary="Anular una orden sin resultado")
def anular(
    orden_id: int, datos: AnulacionIn, c: Contenedor = Depends(contenedor), medico: Usuario = Depends(_medico)
) -> OrdenOut:
    return ordenes_out(c, [c.ordenes.anular(orden_id, medico, datos.motivo)])[0]


@router.post("/{orden_id}/resultado", response_model=OrdenOut, summary="Registrar el resultado de una orden")
def resultado(
    orden_id: int, datos: ResultadoIn, c: Contenedor = Depends(contenedor), usuario: Usuario = Depends(_clinico)
) -> OrdenOut:
    valores = [ResultadoValor(v.parametro, v.valor, v.unidad, v.ref_min, v.ref_max) for v in datos.valores]
    return ordenes_out(c, [c.ordenes.registrar_resultado(orden_id, usuario, valores, datos.interpretacion)])[0]
