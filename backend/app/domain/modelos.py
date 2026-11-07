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
    LABORATORIO = "LABORATORIO"  # apoyo diagnóstico: recibe órdenes y registra resultados


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


class TipoDocumentoElectronico(str, Enum):
    FACTURA = "FACTURA"
    NOTA_CREDITO = "NOTA_CREDITO"


class EstadoDocumentoElectronico(str, Enum):
    GENERADO = "GENERADO"  # creado localmente, aún sin respuesta del proveedor
    ACEPTADO = "ACEPTADO"
    RECHAZADO = "RECHAZADO"


class ConceptoNotaCredito(str, Enum):
    ANULACION = "ANULACION"  # deja sin efecto la factura completa
    GLOSA = "GLOSA"  # descuenta una glosa que la IPS aceptó


class EstadoCaja(str, Enum):
    ABIERTA = "ABIERTA"
    CERRADA = "CERRADA"


class AreaApoyo(str, Enum):
    """Servicio de apoyo diagnóstico que realiza un procedimiento ordenado por el médico."""

    NINGUNA = "NINGUNA"
    LABORATORIO = "LABORATORIO"
    IMAGENOLOGIA = "IMAGENOLOGIA"
    DIAGNOSTICO = "DIAGNOSTICO"  # electrocardiograma, espirometría, etc.


class EstadoOrden(str, Enum):
    SOLICITADA = "SOLICITADA"
    REALIZADA = "REALIZADA"
    ANULADA = "ANULADA"


class PrioridadOrden(str, Enum):
    RUTINA = "RUTINA"
    URGENTE = "URGENTE"


class MetodoPago(str, Enum):
    EFECTIVO = "EFECTIVO"
    TARJETA = "TARJETA"
    TRANSFERENCIA = "TRANSFERENCIA"
    EPS = "EPS"


class TipoPagador(str, Enum):
    """Quién paga la cuenta: el propio paciente o un tercero con el que la IPS tiene convenio."""

    PARTICULAR = "PARTICULAR"
    EPS = "EPS"
    ARL = "ARL"
    SOAT = "SOAT"
    PREPAGADA = "PREPAGADA"


class TipoServicio(str, Enum):
    """Clase de servicio del catálogo; decide en qué grupo del RIPS se reporta."""

    CONSULTA = "CONSULTA"
    PROCEDIMIENTO = "PROCEDIMIENTO"
    OTRO_SERVICIO = "OTRO_SERVICIO"


class OrigenPago(str, Enum):
    PACIENTE = "PACIENTE"
    PAGADOR = "PAGADOR"


class ConceptoGlosa(str, Enum):
    """Conceptos generales de glosa (inspirados en el manual único de glosas)."""

    FACTURACION = "FACTURACION"
    TARIFAS = "TARIFAS"
    SOPORTES = "SOPORTES"
    AUTORIZACION = "AUTORIZACION"
    COBERTURA = "COBERTURA"
    PERTINENCIA = "PERTINENCIA"


class EstadoGlosa(str, Enum):
    ABIERTA = "ABIERTA"  # el pagador la formuló y la IPS aún no responde
    RESPONDIDA = "RESPONDIDA"  # la IPS respondió; falta la decisión del pagador
    ACEPTADA = "ACEPTADA"  # la IPS la acepta: ese valor no se cobra
    LEVANTADA = "LEVANTADA"  # el pagador la retira: el valor vuelve a ser cobrable


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
    """Servicio del catálogo con su tarifa base (en pesos colombianos, sin decimales).

    `cups` es el código de la Clasificación Única de Procedimientos en Salud; el
    RIPS lo exige, por eso el catálogo puede guardarlo.
    """

    codigo: str = ""
    nombre: str = ""
    tarifa: int = 0
    cups: str = ""
    tipo_servicio: TipoServicio = TipoServicio.PROCEDIMIENTO
    area_apoyo: AreaApoyo = AreaApoyo.NINGUNA  # distinta de NINGUNA: se puede ordenar y la realiza apoyo diagnóstico


@dataclass
class Pagador(Entidad):
    """Entidad que responde por la cuenta: el paciente (particular) o una EPS, ARL, etc."""

    codigo: str = ""
    nombre: str = ""
    tipo: TipoPagador = TipoPagador.EPS
    nit: str = ""


@dataclass
class Convenio(Entidad):
    """Condiciones pactadas con un pagador (RF-19).

    `porcentaje_tarifa` ajusta la tarifa base (100 = tarifa completa, 90 = 10 % menos).
    El paciente asume `copago_porcentaje` % de la cuenta más la `cuota_moderadora`
    fija; el resto lo debe el pagador. Para el particular el copago es 100 %.
    """

    pagador_id: int = 0
    nombre: str = ""
    porcentaje_tarifa: int = 100
    copago_porcentaje: int = 0
    cuota_moderadora: int = 0
    requiere_autorizacion: bool = False


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
    convenio_id: Optional[int] = None
    numero_autorizacion: str = ""
    diagnostico_principal: str = ""  # código CIE-10, lo registra el médico tratante


@dataclass
class ProcedimientoRealizado(Entidad):
    """Procedimiento hecho al paciente durante un ingreso (RF-16).

    Forma parte de la historia clínica y a la vez es el cargo que se factura. El
    código, el nombre, el CUPS y el valor se copian del catálogo al registrarlo
    (RN-10): un cambio posterior de tarifa no altera lo ya realizado. El valor ya
    incluye el ajuste del convenio del ingreso (RN-14).
    """

    ingreso_id: int = 0
    paciente_id: int = 0
    medico_id: int = 0
    procedimiento_id: int = 0
    codigo: str = ""
    nombre: str = ""
    cups: str = ""
    tipo_servicio: TipoServicio = TipoServicio.PROCEDIMIENTO
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
class PagoFactura:
    """Dinero recibido por una factura, del paciente (copago) o del pagador (abono)."""

    origen: OrigenPago
    metodo: MetodoPago
    valor: int
    fecha: datetime
    referencia: str = ""
    registrado_por_id: int = 0
    recibo_numero: str = ""  # consecutivo del recibo de caja (RC-000001)
    caja_id: Optional[int] = None  # turno de caja en que lo recibió el cajero


@dataclass
class Glosa:
    """Objeción del pagador a una parte de la factura (RF-21)."""

    id: int
    concepto: ConceptoGlosa
    motivo: str
    valor: int
    fecha: datetime
    estado: EstadoGlosa = EstadoGlosa.ABIERTA
    respuesta: str = ""
    fecha_respuesta: Optional[datetime] = None
    nota_resolucion: str = ""
    fecha_resolucion: Optional[datetime] = None


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
    # Copia del convenio al emitir (RN-14): cambiarlo después no altera lo ya facturado.
    pagador_id: Optional[int] = None
    pagador_codigo: str = ""
    pagador_nombre: str = ""
    convenio_id: Optional[int] = None
    convenio_nombre: str = ""
    valor_paciente: int = 0  # lo que debe pagar el paciente (copago y cuota moderadora)
    valor_pagador: int = 0  # lo que debe pagar la EPS u otro pagador
    fecha_radicacion: Optional[datetime] = None
    numero_radicacion: str = ""
    pagos: list[PagoFactura] = field(default_factory=list)
    glosas: list[Glosa] = field(default_factory=list)

    @property
    def numero(self) -> str:
        return f"FAC-{self.id:06d}"

    @property
    def total(self) -> int:
        return sum(linea.subtotal for linea in self.lineas)

    @property
    def radicada(self) -> bool:
        return self.fecha_radicacion is not None

    def pagado(self, origen: OrigenPago) -> int:
        return sum(p.valor for p in self.pagos if p.origen == origen)

    @property
    def glosado_aceptado(self) -> int:
        return sum(g.valor for g in self.glosas if g.estado == EstadoGlosa.ACEPTADA)

    @property
    def glosa_en_disputa(self) -> int:
        return sum(g.valor for g in self.glosas if g.estado in (EstadoGlosa.ABIERTA, EstadoGlosa.RESPONDIDA))

    @property
    def saldo_paciente(self) -> int:
        return self.valor_paciente - self.pagado(OrigenPago.PACIENTE)

    @property
    def saldo_pagador(self) -> int:
        """Lo que el pagador aún debe, sin contar lo que la IPS aceptó perder por glosas."""
        return self.valor_pagador - self.pagado(OrigenPago.PAGADOR) - self.glosado_aceptado

    @property
    def saldo(self) -> int:
        return self.saldo_paciente + self.saldo_pagador

    def saldada(self) -> bool:
        """Sin saldos y sin glosas en disputa: la factura queda cerrada."""
        return self.saldo == 0 and self.glosa_en_disputa == 0


@dataclass
class ResultadoValor:
    """Una línea de un resultado: parámetro medido, valor, unidad y rango de referencia."""

    parametro: str = ""
    valor: str = ""
    unidad: str = ""
    ref_min: Optional[float] = None
    ref_max: Optional[float] = None

    @property
    def alterado(self) -> Optional[bool]:
        """True si el valor numérico queda fuera del rango; None si no se puede comparar."""
        try:
            numero = float(self.valor.replace(",", "."))
        except ValueError:
            return None
        if self.ref_min is None and self.ref_max is None:
            return None
        if self.ref_min is not None and numero < self.ref_min:
            return True
        if self.ref_max is not None and numero > self.ref_max:
            return True
        return False


@dataclass
class OrdenClinica(Entidad):
    """Orden de un servicio de apoyo diagnóstico dada por el médico tratante (RF-23).

    Al registrarse el resultado, el servicio se carga a la cuenta del ingreso como
    procedimiento realizado y queda en la historia clínica.
    """

    ingreso_id: int = 0
    paciente_id: int = 0
    medico_id: int = 0
    procedimiento_id: int = 0
    codigo: str = ""
    nombre: str = ""
    cups: str = ""
    area: AreaApoyo = AreaApoyo.LABORATORIO
    cantidad: int = 1
    prioridad: PrioridadOrden = PrioridadOrden.RUTINA
    indicacion: str = ""
    fecha: Optional[datetime] = None
    estado: EstadoOrden = EstadoOrden.SOLICITADA
    valores: list[ResultadoValor] = field(default_factory=list)
    interpretacion: str = ""
    fecha_resultado: Optional[datetime] = None
    registrado_por_id: Optional[int] = None
    realizado_id: Optional[int] = None  # cargo generado en la cuenta al registrar el resultado
    motivo_anulacion: str = ""


@dataclass
class EventoDocumento:
    """Una línea del historial de estados de un documento electrónico."""

    fecha: datetime
    estado: EstadoDocumentoElectronico
    mensaje: str = ""


@dataclass
class DocumentoElectronico(Entidad):
    """Factura electrónica o nota crédito de una factura (RF-25, RF-26).

    Lo que se genera aquí es el documento (numeración, CUFE/CUDE, XML UBL 2.1 y QR) y su
    estado ante el proveedor tecnológico. El XML no lleva firma electrónica.
    """

    factura_id: int = 0
    tipo: TipoDocumentoElectronico = TipoDocumentoElectronico.FACTURA
    prefijo: str = ""
    consecutivo: int = 0
    fecha: Optional[datetime] = None
    adquirente_tipo_documento: str = ""  # código DIAN: 13 cédula, 31 NIT, 22 extranjería...
    adquirente_documento: str = ""
    adquirente_dv: str = ""
    adquirente_nombre: str = ""
    adquirente_es_pagador: bool = False
    valor_bruto: int = 0  # suma de las líneas (antes de descontar lo que paga el paciente)
    valor: int = 0  # valor a pagar por el adquirente
    cufe: str = ""  # CUFE (factura) o CUDE (nota crédito), SHA-384
    xml: str = ""
    qr: str = ""
    estado: EstadoDocumentoElectronico = EstadoDocumentoElectronico.GENERADO
    codigo_respuesta: str = ""
    mensaje_respuesta: str = ""
    intentos: int = 0
    eventos: list[EventoDocumento] = field(default_factory=list)
    # Solo para notas crédito
    documento_referencia_id: Optional[int] = None
    concepto: Optional[ConceptoNotaCredito] = None
    motivo: str = ""
    glosa_id: Optional[int] = None

    @property
    def numero(self) -> str:
        return f"{self.prefijo}{self.consecutivo}"


@dataclass
class Caja(Entidad):
    """Turno de caja de un cajero: se abre con una base y se cierra contando el efectivo (RF-27)."""

    cajero_id: int = 0
    fecha_apertura: Optional[datetime] = None
    base_inicial: int = 0
    estado: EstadoCaja = EstadoCaja.ABIERTA
    fecha_cierre: Optional[datetime] = None
    efectivo_esperado: Optional[int] = None
    efectivo_contado: Optional[int] = None
    diferencia: Optional[int] = None
    observaciones: str = ""
    por_metodo: dict[str, int] = field(default_factory=dict)  # instantánea al cerrar
