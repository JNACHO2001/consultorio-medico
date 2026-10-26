from datetime import date

from fastapi import APIRouter, Depends, Query

from app.api.deps import contenedor, requiere_roles
from app.api.mapeos import agenda_item_out
from app.api.schemas import (
    AgendaItemOut,
    CancelarIn,
    CitaIn,
    CitaOut,
    HorariosOut,
    ReprogramarIn,
)
from app.container import Contenedor
from app.domain.excepciones import Prohibido
from app.domain.modelos import Rol, Usuario

router = APIRouter(prefix="/api/citas", tags=["Citas"])


@router.get("/horarios-libres", response_model=HorariosOut, summary="Horarios libres de un médico")
def horarios_libres(
    medico_id: int,
    fecha: date,
    c: Contenedor = Depends(contenedor),
    _: Usuario = Depends(requiere_roles(Rol.RECEPCION)),
) -> HorariosOut:
    horarios = c.citas.consultar_horarios_libres(medico_id, fecha)
    return HorariosOut(medico_id=medico_id, fecha=fecha, horarios=horarios)


@router.get("/agenda", response_model=list[AgendaItemOut], summary="Agenda diaria o semanal (CU-06)")
def consultar_agenda(
    medico_id: int,
    fecha: date,
    dias: int = Query(1, ge=1, le=7, description="1 = diaria, 7 = semanal"),
    c: Contenedor = Depends(contenedor),
    usuario: Usuario = Depends(requiere_roles(Rol.RECEPCION, Rol.MEDICO)),
) -> list[AgendaItemOut]:
    if usuario.rol == Rol.MEDICO and usuario.id != medico_id:
        raise Prohibido("Un médico solo puede consultar su propia agenda.")
    return [agenda_item_out(cita, paciente) for cita, paciente in c.citas.consultar_agenda(medico_id, fecha, dias)]


@router.post("", response_model=CitaOut, status_code=201, summary="Agendar cita (CU-04)")
def agendar_cita(
    datos: CitaIn,
    c: Contenedor = Depends(contenedor),
    _: Usuario = Depends(requiere_roles(Rol.RECEPCION)),
) -> CitaOut:
    cita = c.citas.agendar_cita(datos.paciente_id, datos.medico_id, datos.fecha_hora)
    return CitaOut.model_validate(cita)


@router.put("/{cita_id}/reprogramar", response_model=CitaOut, summary="Reprogramar cita (CU-05)")
def reprogramar_cita(
    cita_id: int,
    datos: ReprogramarIn,
    c: Contenedor = Depends(contenedor),
    _: Usuario = Depends(requiere_roles(Rol.RECEPCION)),
) -> CitaOut:
    return CitaOut.model_validate(c.citas.reprogramar_cita(cita_id, datos.fecha_hora))


@router.post("/{cita_id}/cancelar", response_model=CitaOut, summary="Cancelar cita (CU-05)")
def cancelar_cita(
    cita_id: int,
    datos: CancelarIn,
    c: Contenedor = Depends(contenedor),
    _: Usuario = Depends(requiere_roles(Rol.RECEPCION)),
) -> CitaOut:
    return CitaOut.model_validate(c.citas.cancelar_cita(cita_id, datos.motivo))
