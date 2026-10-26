from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.api.deps import contenedor, requiere_roles
from app.api.mapeos import consulta_out, ingresos_out
from app.api.schemas import (
    ConsultaOut,
    IngresoDetalleOut,
    PacienteIn,
    PacienteOut,
    PacienteResumen,
    PacienteUpdate,
)
from app.container import Contenedor
from app.domain.modelos import Rol, Usuario

router = APIRouter(prefix="/api/pacientes", tags=["Pacientes"])


@router.post("", response_model=PacienteOut, status_code=201, summary="Registrar paciente (CU-02)")
def registrar_paciente(
    datos: PacienteIn,
    c: Contenedor = Depends(contenedor),
    _: Usuario = Depends(requiere_roles(Rol.RECEPCION)),
) -> PacienteOut:
    paciente = c.pacientes.registrar_paciente(**datos.model_dump())
    return PacienteOut.model_validate(paciente)


@router.get("", response_model=list[PacienteResumen], summary="Listar todos los pacientes o buscar (CU-03)")
def buscar_pacientes(
    q: Optional[str] = Query(None, max_length=100, description="Documento o nombre; vacío = todos"),
    c: Contenedor = Depends(contenedor),
    _: Usuario = Depends(requiere_roles(Rol.RECEPCION, Rol.MEDICO)),
) -> list[PacienteResumen]:
    if q is not None and q.strip():
        pacientes = c.pacientes.buscar_paciente(q)
    else:
        pacientes = c.pacientes.listar_pacientes()
    return [PacienteResumen.model_validate(p) for p in pacientes]


@router.get("/{paciente_id}", response_model=PacienteOut, summary="Ver datos de un paciente")
def obtener_paciente(
    paciente_id: int,
    c: Contenedor = Depends(contenedor),
    _: Usuario = Depends(requiere_roles(Rol.RECEPCION, Rol.MEDICO)),
) -> PacienteOut:
    return PacienteOut.model_validate(c.pacientes.obtener_paciente(paciente_id))


@router.put("/{paciente_id}", response_model=PacienteOut, summary="Actualizar datos del paciente")
def actualizar_paciente(
    paciente_id: int,
    datos: PacienteUpdate,
    c: Contenedor = Depends(contenedor),
    usuario: Usuario = Depends(requiere_roles(Rol.RECEPCION)),
) -> PacienteOut:
    paciente = c.pacientes.actualizar_paciente(
        paciente_id, usuario.id, **datos.model_dump(exclude_unset=True)
    )
    return PacienteOut.model_validate(paciente)


@router.get(
    "/{paciente_id}/historial",
    response_model=list[ConsultaOut],
    summary="Consultar historia clínica (CU-08)",
)
def consultar_historial(
    paciente_id: int,
    c: Contenedor = Depends(contenedor),
    _: Usuario = Depends(requiere_roles(Rol.MEDICO)),
) -> list[ConsultaOut]:
    return [consulta_out(c, k) for k in c.consultas.consultar_historial(paciente_id)]


@router.get(
    "/{paciente_id}/ingresos",
    response_model=list[IngresoDetalleOut],
    summary="Ingresos del paciente con sus procedimientos (parte de la historia clínica)",
)
def ingresos_del_paciente(
    paciente_id: int,
    c: Contenedor = Depends(contenedor),
    usuario: Usuario = Depends(requiere_roles(Rol.RECEPCION, Rol.MEDICO)),
) -> list[IngresoDetalleOut]:
    c.pacientes.obtener_paciente(paciente_id)
    ingresos = c.ingresos.buscar(paciente_id=paciente_id)
    return ingresos_out(c, ingresos, clinico=usuario.rol == Rol.MEDICO, detalle=True)
