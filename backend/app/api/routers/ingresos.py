from typing import Optional

from fastapi import APIRouter, Depends

from app.api.deps import contenedor, requiere_roles
from app.api.mapeos import ingresos_out, realizados_out
from app.api.schemas import (
    AnulacionIn,
    EgresoIn,
    IngresoDetalleOut,
    IngresoIn,
    IngresoOut,
    RealizadoIn,
    RealizadoOut,
)
from app.container import Contenedor
from app.domain.modelos import EstadoIngreso, Rol, Usuario

router = APIRouter(prefix="/api/ingresos", tags=["Ingresos y procedimientos"])

_recepcion = requiere_roles(Rol.RECEPCION)
_medico = requiere_roles(Rol.MEDICO)
_recepcion_o_medico = requiere_roles(Rol.RECEPCION, Rol.MEDICO)


def _detalle(c: Contenedor, ingreso_id: int, usuario: Usuario) -> IngresoDetalleOut:
    ingreso = c.ingresos.obtener(ingreso_id)
    return ingresos_out(c, [ingreso], clinico=usuario.rol == Rol.MEDICO, detalle=True)[0]


@router.post("", response_model=IngresoDetalleOut, status_code=201, summary="Admitir al paciente (ingreso)")
def admitir(
    datos: IngresoIn, c: Contenedor = Depends(contenedor), usuario: Usuario = Depends(_recepcion)
) -> IngresoDetalleOut:
    ingreso = c.ingresos.admitir(datos.paciente_id, datos.medico_id, datos.tipo, datos.motivo, usuario)
    return _detalle(c, ingreso.id, usuario)


@router.get("", response_model=list[IngresoOut], summary="Listar ingresos")
def listar(
    estado: Optional[EstadoIngreso] = None,
    medico_id: Optional[int] = None,
    paciente_id: Optional[int] = None,
    c: Contenedor = Depends(contenedor),
    usuario: Usuario = Depends(_recepcion_o_medico),
) -> list[IngresoOut]:
    ingresos = c.ingresos.buscar(estado, medico_id, paciente_id)
    return ingresos_out(c, ingresos, clinico=usuario.rol == Rol.MEDICO)


@router.get("/{ingreso_id}", response_model=IngresoDetalleOut, summary="Cuenta del ingreso con sus procedimientos")
def ver(
    ingreso_id: int, c: Contenedor = Depends(contenedor), usuario: Usuario = Depends(_recepcion_o_medico)
) -> IngresoDetalleOut:
    return _detalle(c, ingreso_id, usuario)


@router.post(
    "/{ingreso_id}/procedimientos",
    response_model=RealizadoOut,
    status_code=201,
    summary="Registrar un procedimiento realizado (queda en la historia clínica y en la cuenta)",
)
def registrar_procedimiento(
    ingreso_id: int,
    datos: RealizadoIn,
    c: Contenedor = Depends(contenedor),
    medico: Usuario = Depends(_medico),
) -> RealizadoOut:
    realizado = c.ingresos.registrar_procedimiento(
        ingreso_id, medico, datos.procedimiento_id, datos.cantidad, datos.observaciones
    )
    return realizados_out(c, [realizado], clinico=True)[0]


@router.post(
    "/{ingreso_id}/procedimientos/{realizado_id}/anular",
    response_model=RealizadoOut,
    summary="Anular un procedimiento registrado por error",
)
def anular_procedimiento(
    ingreso_id: int,
    realizado_id: int,
    datos: AnulacionIn,
    c: Contenedor = Depends(contenedor),
    medico: Usuario = Depends(_medico),
) -> RealizadoOut:
    realizado = c.ingresos.anular_procedimiento(ingreso_id, realizado_id, medico, datos.motivo)
    return realizados_out(c, [realizado], clinico=True)[0]


@router.post("/{ingreso_id}/egreso", response_model=IngresoDetalleOut, summary="Dar el egreso (alta) al paciente")
def dar_egreso(
    ingreso_id: int,
    datos: EgresoIn,
    c: Contenedor = Depends(contenedor),
    medico: Usuario = Depends(_medico),
) -> IngresoDetalleOut:
    c.ingresos.dar_egreso(ingreso_id, medico, datos.resumen)
    return _detalle(c, ingreso_id, medico)
