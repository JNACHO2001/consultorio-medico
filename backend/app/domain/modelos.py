"""Modelo de dominio del consultorio.

Refleja el diagrama de clases (docs/uml/02a_clases_dominio.puml). Son clases
puras de Python, sin dependencias de FastAPI ni de la base de datos.

Nota sobre HistoriaClinica: en el prototipo la historia clínica de un paciente
es el conjunto de sus Consulta (se obtiene con IConsultaRepository.obtener_por_paciente).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Optional


class Rol(str, Enum):
    RECEPCION = "RECEPCION"
    MEDICO = "MEDICO"
    ADMINISTRADOR = "ADMINISTRADOR"


class EstadoCita(str, Enum):
    PROGRAMADA = "PROGRAMADA"
    CANCELADA = "CANCELADA"
    ATENDIDA = "ATENDIDA"


class EstadoRecordatorio(str, Enum):
    PROGRAMADO = "PROGRAMADO"
    ENVIADO = "ENVIADO"
    CANCELADO = "CANCELADO"


@dataclass
class Entidad:
    """Base de todas las entidades persistentes.

    `activo=False` implementa el borrado lógico (RNF-11): los registros no se
    eliminan físicamente.
    """

    id: int = 0
    activo: bool = True


@dataclass
class Usuario(Entidad):
    nombre_usuario: str = ""
    contrasena_hash: str = ""
    nombre_completo: str = ""
    rol: Rol = Rol.RECEPCION


@dataclass
class Medico(Usuario):
    especialidad: str = "Medicina general"
    registro_medico: str = ""

    def __post_init__(self) -> None:
        self.rol = Rol.MEDICO


@dataclass
class CambioPaciente:
    """Registro de un cambio en los datos de un paciente (RF-04)."""

    campo: str
    valor_anterior: Optional[str]
    valor_nuevo: Optional[str]
    usuario_id: int
    fecha: datetime


@dataclass
class Paciente(Entidad):
    tipo_documento: str = "CC"
    numero_documento: str = ""
    nombres: str = ""
    apellidos: str = ""
    fecha_nacimiento: Optional[date] = None
    sexo: str = ""
    telefono: str = ""
    correo: str = ""
    eps: str = ""
    alergias: str = ""
    historial_cambios: list[CambioPaciente] = field(default_factory=list)

    @property
    def nombre_completo(self) -> str:
        return f"{self.nombres} {self.apellidos}".strip()


@dataclass
class Cita(Entidad):
    paciente_id: int = 0
    medico_id: int = 0
    fecha_hora: Optional[datetime] = None
    estado: EstadoCita = EstadoCita.PROGRAMADA
    motivo_cancelacion: Optional[str] = None


@dataclass
class NotaAclaratoria:
    """Corrección posterior a una consulta cerrada (RN-04)."""

    texto: str
    fecha: datetime
    autor_id: int


@dataclass
class Consulta(Entidad):
    cita_id: int = 0
    paciente_id: int = 0
    medico_id: int = 0
    fecha_hora: Optional[datetime] = None
    motivo: str = ""
    antecedentes: str = ""
    signos_vitales: str = ""
    diagnostico: str = ""
    tratamiento: str = ""
    formula: str = ""
    observaciones: str = ""
    cerrada: bool = False
    notas: list[NotaAclaratoria] = field(default_factory=list)


@dataclass
class RegistroAuditoria(Entidad):
    fecha_hora: Optional[datetime] = None
    usuario_id: int = 0
    usuario: str = ""
    accion: str = ""
    entidad: str = ""
    id_entidad: int = 0


@dataclass
class Recordatorio(Entidad):
    """Recordatorio de cita pendiente de envío (RF-10)."""

    cita_id: int = 0
    destinatario: str = ""
    canal: str = "CORREO"
    fecha_envio: Optional[datetime] = None
    estado: EstadoRecordatorio = EstadoRecordatorio.PROGRAMADO
