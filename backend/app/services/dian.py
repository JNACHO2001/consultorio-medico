"""Documentos electrónicos DIAN: CUFE/CUDE, XML UBL 2.1, código QR y proveedor tecnológico.

Qué hace y qué no hace este módulo:

* El CUFE (factura) y el CUDE (nota crédito) se calculan con las fórmulas SHA-384 del
  anexo técnico de la DIAN.
* El XML sigue la estructura general de UBL 2.1 de la factura de venta y la nota crédito,
  con un bloque simplificado de datos del sector salud. No es el XML completo del anexo
  técnico y NO lleva firma electrónica XAdES, que exige un certificado digital.
* `IProveedorTecnologico` es el puerto hacia el proveedor que transmite a la DIAN
  (patrón Adapter). `ProveedorSimulado` valida reglas básicas en local y responde sin
  salir a internet; un proveedor real implementaría la misma interfaz.
"""
from __future__ import annotations

import hashlib
import re
import xml.etree.ElementTree as ET
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from app.config import Configuracion
from app.domain.modelos import DocumentoElectronico, TipoDocumentoElectronico

NS = {
    "": "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2",
    "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
    "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
    "ext": "urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2",
}
NS_NOTA = "urn:oasis:names:specification:ubl:schema:xsd:CreditNote-2"
URL_QR = {"1": "https://catalogo-vpfe.dian.gov.co/document/searchqr?documentkey=",
          "2": "https://catalogo-vpfe-hab.dian.gov.co/document/searchqr?documentkey="}

# Códigos DIAN del tipo de documento del adquirente.
TIPO_DOCUMENTO_DIAN = {"CC": "13", "TI": "12", "CE": "22", "PA": "41", "RC": "11"}
TIPO_NIT = "31"


def _dinero(valor: int) -> str:
    return f"{valor:.2f}"


def desplazamiento(zona: str, fecha: datetime) -> str:
    """Desfase horario de la zona (por ejemplo -05:00), como lo exige la hora del documento."""
    local = fecha.replace(tzinfo=ZoneInfo(zona)) if fecha.tzinfo is None else fecha.astimezone(ZoneInfo(zona))
    texto = local.strftime("%z")
    return f"{texto[:3]}:{texto[3:]}"


def _fecha_hora(fecha: datetime, zona: str) -> tuple[str, str]:
    return fecha.strftime("%Y-%m-%d"), f"{fecha.strftime('%H:%M:%S')}{desplazamiento(zona, fecha)}"


def calcular_cufe(
    numero: str, fecha: datetime, valor_factura: int, valor_total: int, nit_emisor: str,
    tipo_adquirente: str, documento_adquirente: str, clave_tecnica: str, ambiente: str, zona: str = "America/Bogota",
) -> str:
    """CUFE = SHA-384(NumFac+FecFac+HorFac+ValFac+01+ValImp1+04+ValImp2+03+ValImp3+ValTot+NitOFE+TipAdq+NumAdq+ClTec+TipoAmb).

    La atención en salud va excluida de IVA, INC e ICA: los tres impuestos van en 0,00.
    """
    fec, hor = _fecha_hora(fecha, zona)
    cadena = (
        f"{numero}{fec}{hor}{_dinero(valor_factura)}01{_dinero(0)}04{_dinero(0)}03{_dinero(0)}"
        f"{_dinero(valor_total)}{nit_emisor}{tipo_adquirente}{documento_adquirente}{clave_tecnica}{ambiente}"
    )
    return hashlib.sha384(cadena.encode("utf-8")).hexdigest()


def calcular_cude(
    numero: str, fecha: datetime, valor_nota: int, valor_total: int, nit_emisor: str,
    documento_adquirente: str, pin_software: str, ambiente: str, zona: str = "America/Bogota",
) -> str:
    """CUDE de la nota crédito: igual al CUFE pero con el PIN del software en vez de la clave técnica."""
    fec, hor = _fecha_hora(fecha, zona)
    cadena = (
        f"{numero}{fec}{hor}{_dinero(valor_nota)}01{_dinero(0)}04{_dinero(0)}03{_dinero(0)}"
        f"{_dinero(valor_total)}{nit_emisor}{documento_adquirente}{pin_software}{ambiente}"
    )
    return hashlib.sha384(cadena.encode("utf-8")).hexdigest()


def nit_sin_dv(nit: str) -> tuple[str, str]:
    """Separa '800000001-1' en ('800000001', '1')."""
    numero, _, dv = (nit or "").strip().partition("-")
    return re.sub(r"\D", "", numero), dv.strip()


def generar_qr(doc: DocumentoElectronico, nit_emisor: str, ambiente: str, zona: str) -> str:
    fec, hor = _fecha_hora(doc.fecha, zona)
    return "\n".join(
        [
            f"NumFac: {doc.numero}", f"FecFac: {fec}", f"HorFac: {hor}", f"NitFac: {nit_emisor}",
            f"DocAdq: {doc.adquirente_documento}", f"ValFac: {_dinero(doc.valor_bruto)}", f"ValIva: {_dinero(0)}",
            f"ValOtroIm: {_dinero(0)}", f"ValTolFac: {_dinero(doc.valor)}", f"CUFE: {doc.cufe}",
            f"{URL_QR.get(ambiente, URL_QR['2'])}{doc.cufe}",
        ]
    )


@dataclass
class LineaXml:
    consecutivo: int
    codigo: str  # CUPS si lo tiene; si no, el código interno
    descripcion: str
    cantidad: int
    valor_unitario: int
    subtotal: int


@dataclass
class DatosXml:
    """Todo lo que el XML necesita, ya resuelto por el servicio."""

    documento: DocumentoElectronico
    lineas: list[LineaXml]
    emisor_nombre: str
    emisor_nit: str
    emisor_dv: str
    codigo_habilitacion: str
    usuario_documento: str
    usuario_nombre: str
    valor_paciente: int
    numero_autorizacion: str
    # Solo nota crédito
    factura_numero: str = ""
    factura_cufe: str = ""
    factura_fecha: str = ""


def _el(padre: ET.Element, etiqueta: str, texto: str | None = None, **atributos: str) -> ET.Element:
    prefijo, _, nombre = etiqueta.partition(":")
    uri = NS[prefijo] if nombre else NS[""]
    hijo = ET.SubElement(padre, f"{{{uri}}}{nombre or prefijo}", atributos)
    if texto is not None:
        hijo.text = texto
    return hijo


def generar_xml(datos: DatosXml, config: Configuracion) -> str:
    """XML UBL 2.1 de la factura de venta o de la nota crédito (sin firma electrónica)."""
    doc = datos.documento
    es_nota = doc.tipo == TipoDocumentoElectronico.NOTA_CREDITO
    for prefijo, uri in NS.items():
        ET.register_namespace(prefijo, uri if not (prefijo == "" and es_nota) else NS_NOTA)
    raiz = ET.Element(f"{{{NS_NOTA if es_nota else NS['']}}}{'CreditNote' if es_nota else 'Invoice'}")
    fec, hor = _fecha_hora(doc.fecha, config.zona_horaria)

    ext = _el(raiz, "ext:UBLExtensions")
    dian = _el(_el(_el(ext, "ext:UBLExtension"), "ext:ExtensionContent"), "ext:DianExtensions")
    if not es_nota:
        control = _el(dian, "ext:InvoiceControl")
        _el(control, "ext:InvoiceAuthorization", config.dian_resolucion)
        rango = _el(control, "ext:AuthorizationPeriod")
        _el(rango, "ext:Prefix", config.dian_prefijo)
        _el(rango, "ext:From", str(config.dian_rango_desde))
        _el(rango, "ext:To", str(config.dian_rango_hasta))
    _el(dian, "ext:QRCode", doc.qr)
    salud = _el(_el(_el(ext, "ext:UBLExtension"), "ext:ExtensionContent"), "ext:SectorSalud")
    for nombre, valor in (
        ("CODIGO_PRESTADOR", datos.codigo_habilitacion), ("USUARIO_DOCUMENTO", datos.usuario_documento),
        ("USUARIO_NOMBRE", datos.usuario_nombre), ("NUMERO_AUTORIZACION", datos.numero_autorizacion),
        ("VALOR_A_CARGO_DEL_PACIENTE", _dinero(datos.valor_paciente)),
    ):
        info = _el(salud, "ext:AdditionalInformation")
        _el(info, "cbc:Name", nombre)
        _el(info, "cbc:Value", valor or "")

    _el(raiz, "cbc:UBLVersionID", "UBL 2.1")
    _el(raiz, "cbc:CustomizationID", "20" if es_nota else "10")
    _el(raiz, "cbc:ProfileID", "DIAN 2.1: Nota Crédito de Factura Electrónica de Venta" if es_nota
        else "DIAN 2.1: Factura Electrónica de Venta")
    _el(raiz, "cbc:ProfileExecutionID", config.dian_ambiente)
    _el(raiz, "cbc:ID", doc.numero)
    _el(raiz, "cbc:UUID", doc.cufe, schemeName="CUDE-SHA384" if es_nota else "CUFE-SHA384")
    _el(raiz, "cbc:IssueDate", fec)
    _el(raiz, "cbc:IssueTime", hor)
    if es_nota:
        _el(raiz, "cbc:CreditNoteTypeCode", "91")
    else:
        _el(raiz, "cbc:InvoiceTypeCode", "01")
    if doc.motivo:
        _el(raiz, "cbc:Note", doc.motivo)
    _el(raiz, "cbc:DocumentCurrencyCode", "COP")
    _el(raiz, "cbc:LineCountNumeric", str(len(datos.lineas)))

    if es_nota:
        ref = _el(_el(raiz, "cac:BillingReference"), "cac:InvoiceDocumentReference")
        _el(ref, "cbc:ID", datos.factura_numero)
        _el(ref, "cbc:UUID", datos.factura_cufe, schemeName="CUFE-SHA384")
        _el(ref, "cbc:IssueDate", datos.factura_fecha)

    emisor = _el(_el(raiz, "cac:AccountingSupplierParty"), "cac:Party")
    _el(_el(emisor, "cac:PartyName"), "cbc:Name", datos.emisor_nombre)
    _el(_el(emisor, "cac:PartyTaxScheme"), "cbc:CompanyID", datos.emisor_nit, schemeID=datos.emisor_dv, schemeName="31")

    cliente = _el(_el(raiz, "cac:AccountingCustomerParty"), "cac:Party")
    _el(_el(cliente, "cac:PartyName"), "cbc:Name", doc.adquirente_nombre)
    _el(_el(cliente, "cac:PartyTaxScheme"), "cbc:CompanyID", doc.adquirente_documento,
        schemeID=doc.adquirente_dv, schemeName=doc.adquirente_tipo_documento)

    pago = _el(raiz, "cac:PaymentMeans")
    _el(pago, "cbc:ID", "2" if doc.adquirente_es_pagador else "1")  # 1 contado, 2 crédito
    impuestos = _el(raiz, "cac:TaxTotal")
    _el(impuestos, "cbc:TaxAmount", _dinero(0), currencyID="COP")
    total = _el(raiz, "cac:LegalMonetaryTotal")
    for etiqueta, valor in (
        ("cbc:LineExtensionAmount", doc.valor_bruto), ("cbc:TaxExclusiveAmount", doc.valor_bruto),
        ("cbc:TaxInclusiveAmount", doc.valor_bruto), ("cbc:PrepaidAmount", datos.valor_paciente),
        ("cbc:PayableAmount", doc.valor),
    ):
        _el(total, etiqueta, _dinero(valor), currencyID="COP")

    for linea in datos.lineas:
        nodo = _el(raiz, "cac:CreditNoteLine" if es_nota else "cac:InvoiceLine")
        _el(nodo, "cbc:ID", str(linea.consecutivo))
        _el(nodo, "cbc:CreditedQuantity" if es_nota else "cbc:InvoicedQuantity", str(linea.cantidad), unitCode="94")
        _el(nodo, "cbc:LineExtensionAmount", _dinero(linea.subtotal), currencyID="COP")
        item = _el(nodo, "cac:Item")
        _el(item, "cbc:Description", linea.descripcion)
        _el(_el(item, "cac:StandardItemIdentification"), "cbc:ID", linea.codigo)
        _el(_el(nodo, "cac:Price"), "cbc:PriceAmount", _dinero(linea.valor_unitario), currencyID="COP")

    ET.indent(raiz)
    return '<?xml version="1.0" encoding="UTF-8"?>\n<!-- Borrador estructural UBL 2.1. Sin firma electrónica XAdES. -->\n' + ET.tostring(
        raiz, encoding="unicode"
    )


# ------------------------------------------------------------------ proveedor tecnológico


@dataclass
class RespuestaProveedor:
    aceptado: bool
    codigo: str
    mensaje: str


class IProveedorTecnologico(ABC):
    """Puerto hacia el proveedor que firma, transmite el documento a la DIAN y devuelve su respuesta."""

    nombre: str = ""

    @abstractmethod
    def enviar(self, documento: DocumentoElectronico) -> RespuestaProveedor: ...


class ProveedorSimulado(IProveedorTecnologico):
    """Valida en local las reglas básicas; no transmite nada a la DIAN."""

    nombre = "Proveedor simulado (sin conexión con la DIAN)"

    def __init__(self, config: Configuracion, ahora=None) -> None:
        self._config = config
        self._ahora = ahora or (lambda: datetime.now(ZoneInfo(config.zona_horaria)).replace(tzinfo=None))

    def enviar(self, documento: DocumentoElectronico) -> RespuestaProveedor:
        errores: list[tuple[str, str]] = []
        try:
            ET.fromstring(documento.xml.split("?>", 1)[-1])
        except ET.ParseError:
            errores.append(("SIM-01", "El XML no está bien formado."))
        if not re.fullmatch(r"[0-9a-f]{96}", documento.cufe or ""):
            errores.append(("SIM-02", "El CUFE/CUDE no es un SHA-384 válido."))
        if documento.tipo == TipoDocumentoElectronico.FACTURA and not (
            self._config.dian_rango_desde <= documento.consecutivo <= self._config.dian_rango_hasta
        ):
            errores.append(("SIM-03", "La numeración está fuera del rango autorizado en la resolución."))
        if not re.fullmatch(r"[A-Za-z0-9]{4,20}", documento.adquirente_documento or ""):
            errores.append(("SIM-04", "El adquirente no tiene un número de identificación válido (para una EPS, registre su NIT)."))
        elif documento.adquirente_tipo_documento == TIPO_NIT and not re.fullmatch(r"\d{9,10}", documento.adquirente_documento):
            errores.append(("SIM-04", "El NIT del adquirente debe tener 9 o 10 dígitos."))
        if documento.valor <= 0:
            errores.append(("SIM-05", "El valor del documento debe ser mayor a cero."))
        if documento.fecha and documento.fecha > self._ahora():
            errores.append(("SIM-06", "La fecha de emisión es posterior a la fecha actual."))
        if errores:
            return RespuestaProveedor(False, errores[0][0], " ".join(f"[{c}] {m}" for c, m in errores))
        return RespuestaProveedor(True, "SIM-00", "Documento validado por el proveedor simulado (no se transmitió a la DIAN).")
