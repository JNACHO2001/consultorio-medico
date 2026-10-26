"""Conversión de entidades de dominio a esquemas de salida que necesitan datos extra."""
from typing import Optional

from app.api.schemas import AgendaItemOut, ConsultaOut
from app.container import Contenedor
from app.domain.modelos import Cita, Consulta, Paciente


def consulta_out(c: Contenedor, consulta: Consulta) -> ConsultaOut:
    salida = ConsultaOut.model_validate(consulta)
    medico = c.repo_usuarios.obtener_por_id(consulta.medico_id)
    salida.medico_nombre = medico.nombre_completo if medico else ""
    return salida


def agenda_item_out(cita: Cita, paciente: Optional[Paciente]) -> AgendaItemOut:
    salida = AgendaItemOut.model_validate(cita)
    if paciente is not None:
        salida.paciente_nombre = paciente.nombre_completo
        salida.paciente_documento = f"{paciente.tipo_documento} {paciente.numero_documento}"
    return salida
