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


class TipoIngreso(str, Enum):
    AMBULATORIO = "AMBULATORIO"
    URGENCIAS = "URGENCIAS"
    OBSERVACION = "OBSERVACION"


class EstadoIngreso(str, Enum):
    ABIERTO = "ABIERTO"
    EGRESADO = "EGRESADO"


class EstadoFactura(str, Enum):
    EMITIDA = "EMITIDA"
    PAGADA = "PAGADA"
    ANULADA = "ANULADA"


class MetodoPago(str, Enum):
    EFECTIVO = "EFECTIVO"
    TARJETA = "TARJETA"
    TRANSFERENCIA = "TRANSFERENCIA"
    EPS = "EPS"


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


@dataclass
class Procedimiento(Entidad):
    """Servicio del catálogo con su tarifa vigente (en pesos colombianos, sin decimales)."""

    codigo: str = ""
    nombre: str = ""
    tarifa: int = 0


@dataclass
class Ingreso(Entidad):
    """Admisión del paciente: abre la cuenta a la que se cargan los procedimientos (RF-15)."""

    paciente_id: int = 0
    medico_id: int = 0
    tipo: TipoIngreso = TipoIngreso.AMBULATORIO
    motivo: str = ""
    fecha_ingreso: Optional[datetime] = None
    estado: EstadoIngreso = EstadoIngreso.ABIERTO
    fecha_egreso: Optional[datetime] = None
    resumen_egreso: str = ""
    admitido_por_id: int = 0


@dataclass
class ProcedimientoRealizado(Entidad):
    """Procedimiento hecho al paciente durante un ingreso (RF-16).

    Forma parte de la historia clínica y a la vez es el cargo que se factura. El
    código, el nombre y el valor se copian del catálogo al registrarlo (RN-10): un
    cambio posterior de tarifa no altera lo ya realizado.
    """

    ingreso_id: int = 0
    paciente_id: int = 0
    medico_id: int = 0
    procedimiento_id: int = 0
    codigo: str = ""
    nombre: str = ""
    cantidad: int = 1
    valor_unitario: int = 0
    fecha_hora: Optional[datetime] = None
    observaciones: str = ""
    anulado: bool = False
    motivo_anulacion: str = ""
    factura_id: Optional[int] = None

    @property
    def subtotal(self) -> int:
        return self.cantidad * self.valor_unitario


@dataclass
class LineaFactura:
    procedimiento_realizado_id: int
    codigo: str
    descripcion: str
    cantidad: int
    valor_unitario: int

    @property
    def subtotal(self) -> int:
        return self.cantidad * self.valor_unitario


@dataclass
class Factura(Entidad):
    ingreso_id: int = 0
    paciente_id: int = 0
    fecha: Optional[datetime] = None
    lineas: list[LineaFactura] = field(default_factory=list)
    estado: EstadoFactura = EstadoFactura.EMITIDA
    emitida_por_id: int = 0
    metodo_pago: Optional[MetodoPago] = None
    fecha_pago: Optional[datetime] = None
    motivo_anulacion: str = ""

    @property
    def numero(self) -> str:
        return f"FAC-{self.id:06d}"

    @property
    def total(self) -> int:
        return sum(linea.subtotal for linea in self.lineas)
