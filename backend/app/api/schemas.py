"""Esquemas de entrada y salida de la API (validación de la forma de los datos)."""
from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.domain.modelos import (
    AreaApoyo,
    ConceptoGlosa,
    ConceptoNotaCredito,
    EstadoCaja,
    EstadoCita,
    EstadoDocumentoElectronico,
    EstadoFactura,
    EstadoGlosa,
    EstadoIngreso,
    EstadoOrden,
    EstadoRecordatorio,
    MetodoPago,
    OrigenPago,
    PrioridadOrden,
    Rol,
    TipoDocumentoElectronico,
    TipoIngreso,
    TipoPagador,
    TipoServicio,
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
    tarifa: int = Field(description="Valor base en pesos, sin decimales")
    cups: str = Field("", max_length=6, description="Código CUPS de 6 dígitos (opcional, lo exige el RIPS)")
    tipo_servicio: TipoServicio = TipoServicio.PROCEDIMIENTO
    area_apoyo: AreaApoyo = AreaApoyo.NINGUNA


class ProcedimientoCatalogoUpdate(BaseModel):
    nombre: Optional[str] = Field(None, max_length=120)
    tarifa: Optional[int] = None
    cups: Optional[str] = Field(None, max_length=6)
    tipo_servicio: Optional[TipoServicio] = None
    area_apoyo: Optional[AreaApoyo] = None


class ProcedimientoCatalogoOut(Salida):
    id: int
    codigo: str
    nombre: str
    tarifa: int
    cups: str = ""
    tipo_servicio: TipoServicio = TipoServicio.PROCEDIMIENTO
    area_apoyo: AreaApoyo = AreaApoyo.NINGUNA


# ----------------------------------------------------------------------- pagadores y convenios


class PagadorIn(BaseModel):
    codigo: str = Field(max_length=12)
    nombre: str = Field(max_length=120)
    tipo: TipoPagador = TipoPagador.EPS
    nit: str = Field("", max_length=20)


class PagadorUpdate(BaseModel):
    nombre: Optional[str] = Field(None, max_length=120)
    nit: Optional[str] = Field(None, max_length=20)


class ConvenioIn(BaseModel):
    nombre: str = Field(max_length=120)
    porcentaje_tarifa: int = Field(100, description="100 = tarifa base completa")
    copago_porcentaje: int = Field(0, description="% de la cuenta que paga el paciente")
    cuota_moderadora: int = Field(0, description="Valor fijo en pesos que paga el paciente")
    requiere_autorizacion: bool = False


class ConvenioUpdate(BaseModel):
    nombre: Optional[str] = Field(None, max_length=120)
    porcentaje_tarifa: Optional[int] = None
    copago_porcentaje: Optional[int] = None
    cuota_moderadora: Optional[int] = None
    requiere_autorizacion: Optional[bool] = None


class ConvenioOut(Salida):
    id: int
    pagador_id: int
    nombre: str
    porcentaje_tarifa: int
    copago_porcentaje: int
    cuota_moderadora: int
    requiere_autorizacion: bool
    activo: bool


class PagadorOut(Salida):
    id: int
    codigo: str
    nombre: str
    tipo: TipoPagador
    nit: str
    activo: bool
    convenios: list[ConvenioOut] = []


class IngresoIn(BaseModel):
    paciente_id: int
    medico_id: int
    tipo: TipoIngreso = TipoIngreso.AMBULATORIO
    motivo: str = Field(max_length=500)
    convenio_id: Optional[int] = Field(None, description="Si se omite, se admite como particular")
    numero_autorizacion: str = Field("", max_length=40)


class DiagnosticoIn(BaseModel):
    codigo_cie10: str = Field(max_length=5, description="Código CIE-10 sin punto, por ejemplo J00")


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
    cups: str = ""
    tipo_servicio: TipoServicio = TipoServicio.PROCEDIMIENTO
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
    convenio_id: Optional[int] = None
    convenio_nombre: str = ""
    pagador_nombre: str = ""
    porcentaje_tarifa: int = 100
    numero_autorizacion: str = ""
    diagnostico_principal: Optional[str] = None  # dato clínico: solo lo ve el médico
    diagnostico_descripcion: Optional[str] = None
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


class RadicacionIn(BaseModel):
    numero_radicacion: str = Field("", max_length=40, description="Si se omite, se genera uno")


class PagoPagadorIn(BaseModel):
    valor: int = Field(description="Valor abonado por el pagador, en pesos")
    metodo_pago: MetodoPago = MetodoPago.TRANSFERENCIA
    referencia: str = Field("", max_length=60, description="Comprobante o número de transferencia")


class GlosaIn(BaseModel):
    concepto: ConceptoGlosa
    motivo: str = Field(max_length=500)
    valor: int = Field(description="Valor glosado, en pesos")


class RespuestaGlosaIn(BaseModel):
    respuesta: str = Field(max_length=1000)


class ResolucionGlosaIn(BaseModel):
    aceptada: bool = Field(description="True: la IPS acepta la glosa; False: el pagador la levanta")
    nota: str = Field("", max_length=500)


class LineaFacturaOut(Salida):
    procedimiento_realizado_id: int
    codigo: str
    descripcion: str
    cantidad: int
    valor_unitario: int
    subtotal: int


class PagoFacturaOut(Salida):
    origen: OrigenPago
    metodo: MetodoPago
    valor: int
    fecha: datetime
    referencia: str = ""
    recibo_numero: str = ""
    caja_id: Optional[int] = None


class GlosaOut(Salida):
    id: int
    concepto: ConceptoGlosa
    motivo: str
    valor: int
    fecha: datetime
    estado: EstadoGlosa
    respuesta: str = ""
    fecha_respuesta: Optional[datetime] = None
    nota_resolucion: str = ""
    fecha_resolucion: Optional[datetime] = None


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
    pagador_id: Optional[int] = None
    pagador_nombre: str = ""
    convenio_nombre: str = ""
    valor_paciente: int = 0
    valor_pagador: int = 0
    pagado_paciente: int = 0
    pagado_pagador: int = 0
    saldo_paciente: int = 0
    saldo_pagador: int = 0
    saldo: int = 0
    glosado_aceptado: int = 0
    glosa_en_disputa: int = 0
    fecha_radicacion: Optional[datetime] = None
    numero_radicacion: str = ""
    dias_radicada: Optional[int] = None
    pagos: list[PagoFacturaOut] = []
    glosas: list[GlosaOut] = []
    # Facturación electrónica: factura vigente y notas crédito (sin XML; se descarga aparte)
    factura_electronica: Optional["DocumentoResumenOut"] = None
    notas_credito: list["DocumentoResumenOut"] = []
    dian_obligatoria: bool = False


class TramosCarteraOut(BaseModel):
    sin_radicar: int = 0
    d0_30: int = 0
    d31_60: int = 0
    d61_90: int = 0
    d_mas_90: int = 0


class CarteraPagadorOut(BaseModel):
    pagador_id: int
    pagador_nombre: str
    n_facturas: int
    facturado: int
    recaudado: int
    glosa_aceptada: int
    en_disputa: int
    saldo: int
    tramos: TramosCarteraOut


class CarteraDetalleOut(BaseModel):
    resumen: Optional[CarteraPagadorOut] = None
    facturas: list[FacturaOut] = []


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


# ----------------------------------------------------------------------- CIE-10, órdenes y resultados


class Cie10Out(BaseModel):
    codigo: str
    descripcion: str


class OrdenIn(BaseModel):
    ingreso_id: int
    procedimiento_id: int
    cantidad: int = Field(1, ge=1, le=99)
    prioridad: PrioridadOrden = PrioridadOrden.RUTINA
    indicacion: str = Field("", max_length=500, description="Motivo clínico o indicación para quien realiza el examen")


class ResultadoValorIn(BaseModel):
    parametro: str = Field(max_length=80)
    valor: str = Field(max_length=60)
    unidad: str = Field("", max_length=20)
    ref_min: Optional[float] = None
    ref_max: Optional[float] = None


class ResultadoValorOut(ResultadoValorIn):
    model_config = ConfigDict(from_attributes=True)

    alterado: Optional[bool] = None


class ResultadoIn(BaseModel):
    valores: list[ResultadoValorIn] = []
    interpretacion: str = Field("", max_length=3000)


class OrdenOut(Salida):
    id: int
    ingreso_id: int
    paciente_id: int
    paciente_nombre: str = ""
    paciente_documento: str = ""
    medico_id: int
    medico_nombre: str = ""
    procedimiento_id: int
    codigo: str
    nombre: str
    cups: str = ""
    area: AreaApoyo
    cantidad: int
    prioridad: PrioridadOrden
    indicacion: str = ""
    fecha: Optional[datetime] = None
    estado: EstadoOrden
    valores: list[ResultadoValorOut] = []
    interpretacion: str = ""
    fecha_resultado: Optional[datetime] = None
    registrado_por: str = ""
    motivo_anulacion: str = ""
    alterada: bool = False


# ------------------------------------------------------------- facturación electrónica y caja


class EventoDocumentoOut(Salida):
    fecha: datetime
    estado: EstadoDocumentoElectronico
    mensaje: str


class DocumentoResumenOut(Salida):
    id: int
    factura_id: int
    tipo: TipoDocumentoElectronico
    numero: str
    fecha: Optional[datetime] = None
    estado: EstadoDocumentoElectronico
    cufe: str = ""
    valor: int = 0
    valor_bruto: int = 0
    adquirente_nombre: str = ""
    adquirente_documento: str = ""
    adquirente_dv: str = ""
    adquirente_es_pagador: bool = False
    codigo_respuesta: str = ""
    mensaje_respuesta: str = ""
    intentos: int = 0
    concepto: Optional[ConceptoNotaCredito] = None
    motivo: str = ""
    glosa_id: Optional[int] = None
    documento_referencia_id: Optional[int] = None


class DocumentoElectronicoOut(DocumentoResumenOut):
    factura_numero: str = ""
    paciente_nombre: str = ""
    qr: str = ""
    eventos: list[EventoDocumentoOut] = []


class NotaCreditoIn(BaseModel):
    concepto: ConceptoNotaCredito
    motivo: str = Field(default="", max_length=300)
    glosa_id: Optional[int] = None


class AperturaCajaIn(BaseModel):
    base_inicial: int = Field(ge=0, le=100_000_000)


class CierreCajaIn(BaseModel):
    efectivo_contado: int = Field(ge=0, le=1_000_000_000)
    observaciones: str = Field(default="", max_length=300)


class ReciboOut(Salida):
    recibo_numero: str
    factura_id: int
    factura_numero: str
    origen: OrigenPago
    metodo: MetodoPago
    valor: int
    fecha: datetime
    referencia: str = ""
    paciente_nombre: str = ""


class CajaOut(Salida):
    id: int
    cajero_id: int
    cajero_nombre: str = ""
    fecha_apertura: Optional[datetime] = None
    base_inicial: int
    estado: EstadoCaja
    fecha_cierre: Optional[datetime] = None
    efectivo_esperado: Optional[int] = None
    efectivo_contado: Optional[int] = None
    diferencia: Optional[int] = None
    observaciones: str = ""
    por_metodo: dict[str, int] = {}
    n_recibos: int = 0
    total_recibido: int = 0
    efectivo_esperado_actual: int = 0


class CajaDetalleOut(CajaOut):
    recibos: list[ReciboOut] = []


FacturaOut.model_rebuild()
