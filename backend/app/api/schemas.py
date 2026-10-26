"""Esquemas de entrada y salida de la API (validación de la forma de los datos)."""
from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.domain.modelos import (
    EstadoCita,
    EstadoFactura,
    EstadoIngreso,
    EstadoRecordatorio,
    MetodoPago,
    Rol,
    TipoIngreso,
)

TipoDocumento = Literal["CC", "TI", "CE", "PA", "RC"]


class Salida(BaseModel):
    """Base de los esquemas de salida: se construyen a partir de las entidades de dominio."""

    model_config = ConfigDict(from_attributes=True)


# ----------------------------------------------------------------------- sesión y usuarios


class LoginIn(BaseModel):
    usuario: str = Field(max_length=60)
    contrasena: str = Field(max_length=200)


class UsuarioOut(Salida):
    id: int
    nombre_usuario: str
    nombre_completo: str
    rol: Rol
    activo: bool
    especialidad: Optional[str] = None
    registro_medico: Optional[str] = None


class LoginOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expira_en_minutos: int
    usuario: UsuarioOut


class UsuarioIn(BaseModel):
    nombre_usuario: str = Field(max_length=30)
    contrasena: str = Field(max_length=200)
    nombre_completo: str = Field(max_length=120)
    rol: Rol
    especialidad: str = Field("", max_length=80)
    registro_medico: str = Field("", max_length=40)


class MedicoOut(Salida):
    id: int
    nombre_completo: str
    especialidad: Optional[str] = None


# ----------------------------------------------------------------------- pacientes


class PacienteIn(BaseModel):
    tipo_documento: TipoDocumento
    numero_documento: str = Field(max_length=30)
    nombres: str = Field(max_length=100)
    apellidos: str = Field(max_length=100)
    fecha_nacimiento: date
    sexo: str = Field("", max_length=20)
    telefono: str = Field("", max_length=30)
    correo: str = Field("", max_length=120)
    eps: str = Field("", max_length=80)
    alergias: str = Field("", max_length=500)


class PacienteUpdate(BaseModel):
    """El documento no se puede cambiar: es la identidad del paciente (RN-01)."""

    nombres: Optional[str] = Field(None, max_length=100)
    apellidos: Optional[str] = Field(None, max_length=100)
    fecha_nacimiento: Optional[date] = None
    sexo: Optional[str] = Field(None, max_length=20)
    telefono: Optional[str] = Field(None, max_length=30)
    correo: Optional[str] = Field(None, max_length=120)
    eps: Optional[str] = Field(None, max_length=80)
    alergias: Optional[str] = Field(None, max_length=500)


class CambioOut(Salida):
    campo: str
    valor_anterior: Optional[str]
    valor_nuevo: Optional[str]
    usuario_id: int
    fecha: datetime


class PacienteResumen(Salida):
    id: int
    tipo_documento: str
    numero_documento: str
    nombre_completo: str
    eps: str


class PacienteOut(Salida):
    id: int
    tipo_documento: str
    numero_documento: str
    nombres: str
    apellidos: str
    nombre_completo: str
    fecha_nacimiento: Optional[date]
    sexo: str
    telefono: str
    correo: str
    eps: str
    alergias: str
    historial_cambios: list[CambioOut] = []


# ----------------------------------------------------------------------- citas


class CitaIn(BaseModel):
    paciente_id: int
    medico_id: int
    fecha_hora: datetime


class ReprogramarIn(BaseModel):
    fecha_hora: datetime


class CancelarIn(BaseModel):
    motivo: str = Field(max_length=300)


class CitaOut(Salida):
    id: int
    paciente_id: int
    medico_id: int
    fecha_hora: datetime
    estado: EstadoCita
    motivo_cancelacion: Optional[str] = None


class AgendaItemOut(CitaOut):
    paciente_nombre: str = ""
    paciente_documento: str = ""


class HorariosOut(BaseModel):
    medico_id: int
    fecha: date
    horarios: list[datetime]


# ----------------------------------------------------------------------- consultas


class ConsultaIn(BaseModel):
    cita_id: int
    motivo: str = Field(max_length=2000)
    antecedentes: str = Field("", max_length=5000)
    signos_vitales: str = Field("", max_length=1000)
    diagnostico: str = Field("", max_length=5000)
    tratamiento: str = Field("", max_length=5000)
    formula: str = Field("", max_length=5000)
    observaciones: str = Field("", max_length=5000)


class ConsultaUpdate(BaseModel):
    motivo: Optional[str] = Field(None, max_length=2000)
    antecedentes: Optional[str] = Field(None, max_length=5000)
    signos_vitales: Optional[str] = Field(None, max_length=1000)
    diagnostico: Optional[str] = Field(None, max_length=5000)
    tratamiento: Optional[str] = Field(None, max_length=5000)
    formula: Optional[str] = Field(None, max_length=5000)
    observaciones: Optional[str] = Field(None, max_length=5000)


class NotaIn(BaseModel):
    texto: str = Field(max_length=2000)


class NotaOut(Salida):
    texto: str
    fecha: datetime
    autor_id: int


class ConsultaOut(Salida):
    id: int
    cita_id: int
    paciente_id: int
    medico_id: int
    medico_nombre: str = ""
    fecha_hora: Optional[datetime]
    motivo: str
    antecedentes: str
    signos_vitales: str
    diagnostico: str
    tratamiento: str
    formula: str
    observaciones: str
    cerrada: bool
    notas: list[NotaOut] = []


# ----------------------------------------------------------------------- catálogo, ingresos y facturación


class ProcedimientoCatalogoIn(BaseModel):
    codigo: str = Field(max_length=12)
    nombre: str = Field(max_length=120)
    tarifa: int = Field(description="Valor en pesos, sin decimales")


class ProcedimientoCatalogoUpdate(BaseModel):
    nombre: Optional[str] = Field(None, max_length=120)
    tarifa: Optional[int] = None


class ProcedimientoCatalogoOut(Salida):
    id: int
    codigo: str
    nombre: str
    tarifa: int


class IngresoIn(BaseModel):
    paciente_id: int
    medico_id: int
    tipo: TipoIngreso = TipoIngreso.AMBULATORIO
    motivo: str = Field(max_length=500)


class EgresoIn(BaseModel):
    resumen: str = Field("", max_length=3000)


class RealizadoIn(BaseModel):
    procedimiento_id: int
    cantidad: int = Field(1, ge=1, le=99)
    observaciones: str = Field("", max_length=2000)


class AnulacionIn(BaseModel):
    motivo: str = Field(max_length=300)


class RealizadoOut(Salida):
    id: int
    ingreso_id: int
    paciente_id: int
    medico_id: int
    medico_nombre: str = ""
    codigo: str
    nombre: str
    cantidad: int
    valor_unitario: int
    subtotal: int
    fecha_hora: Optional[datetime]
    observaciones: Optional[str] = None  # dato clínico: solo lo ve el médico
    anulado: bool
    motivo_anulacion: str
    factura_id: Optional[int] = None
    factura_numero: Optional[str] = None


class IngresoOut(Salida):
    id: int
    paciente_id: int
    paciente_nombre: str = ""
    paciente_documento: str = ""
    medico_id: int
    medico_nombre: str = ""
    tipo: TipoIngreso
    motivo: str
    fecha_ingreso: Optional[datetime]
    estado: EstadoIngreso
    fecha_egreso: Optional[datetime]
    resumen_egreso: Optional[str] = None  # dato clínico: solo lo ve el médico
    n_procedimientos: int = 0
    total: int = 0
    pendiente_facturar: int = 0


class IngresoDetalleOut(IngresoOut):
    procedimientos: list[RealizadoOut] = []


class FacturaIn(BaseModel):
    ingreso_id: int
    procedimiento_ids: Optional[list[int]] = Field(
        None, description="Procedimientos a facturar; si se omite, todos los pendientes"
    )


class PagoIn(BaseModel):
    metodo_pago: MetodoPago


class LineaFacturaOut(Salida):
    procedimiento_realizado_id: int
    codigo: str
    descripcion: str
    cantidad: int
    valor_unitario: int
    subtotal: int


class FacturaOut(Salida):
    id: int
    numero: str
    ingreso_id: int
    paciente_id: int
    paciente_nombre: str = ""
    paciente_documento: str = ""
    fecha: Optional[datetime]
    estado: EstadoFactura
    lineas: list[LineaFacturaOut]
    total: int
    metodo_pago: Optional[MetodoPago] = None
    fecha_pago: Optional[datetime] = None
    motivo_anulacion: str = ""
    emitida_por: str = ""


# ----------------------------------------------------------------------- auditoría y recordatorios


class AuditoriaOut(Salida):
    id: int
    fecha_hora: datetime
    usuario_id: int
    usuario: str
    accion: str
    entidad: str
    id_entidad: int


class RecordatorioOut(Salida):
    id: int
    cita_id: int
    destinatario: str
    canal: str
    fecha_envio: datetime
    estado: EstadoRecordatorio
