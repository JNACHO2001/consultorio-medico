"""Facturación electrónica: emisión, reintento y notas crédito (RF-25, RF-26).

La factura electrónica se emite al adquirente que debe pagar: la EPS u otro pagador por
su parte (facturación a terceros) o, si no hay pagador, el paciente. Lo que paga el
paciente por copagos y cuotas moderadoras se soporta con recibo de caja.
"""
from __future__ import annotations

import threading
from typing import Optional

from app.config import Configuracion
from app.core.auditoria import auditar
from app.core.tiempo import ahora_local
from app.domain.excepciones import Conflicto, NoEncontrado, ReglaNegocio
from app.domain.modelos import (
    ConceptoNotaCredito,
    DocumentoElectronico,
    EstadoDocumentoElectronico,
    EstadoFactura,
    EstadoGlosa,
    EventoDocumento,
    Factura,
    TipoDocumentoElectronico,
    Usuario,
)
from app.repositories.interfaces import (
    IAuditoriaRepository,
    IDocumentoElectronicoRepository,
    IPacienteRepository,
    IProcedimientoRealizadoRepository,
)
from app.services.convenios import ConvenioService
from app.services.dian import (
    DatosXml,
    IProveedorTecnologico,
    LineaXml,
    TIPO_DOCUMENTO_DIAN,
    TIPO_NIT,
    calcular_cude,
    calcular_cufe,
    generar_qr,
    generar_xml,
    nit_sin_dv,
)
from app.services.facturacion import FacturacionService

PREFIJO_NOTA = "NC"
E = EstadoDocumentoElectronico
T = TipoDocumentoElectronico


class FacturacionElectronicaService:
    def __init__(
        self,
        documentos: IDocumentoElectronicoRepository,
        facturacion: FacturacionService,
        pacientes: IPacienteRepository,
        realizados: IProcedimientoRealizadoRepository,
        convenios: ConvenioService,
        proveedor: IProveedorTecnologico,
        auditoria: IAuditoriaRepository,
        config: Configuracion,
    ) -> None:
        self._documentos = documentos
        self._facturacion = facturacion
        self._pacientes = pacientes
        self._realizados = realizados
        self._convenios = convenios
        self._proveedor = proveedor
        self._auditoria = auditoria
        self._config = config
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ consulta

    @property
    def proveedor(self) -> str:
        return self._proveedor.nombre

    def obtener(self, documento_id: int) -> DocumentoElectronico:
        doc = self._documentos.obtener_por_id(documento_id)
        if doc is None:
            raise NoEncontrado("El documento electrónico no existe.")
        return doc

    def buscar(
        self, factura_id: Optional[int] = None, tipo: Optional[T] = None, estado: Optional[E] = None
    ) -> list[DocumentoElectronico]:
        return self._documentos.buscar(factura_id, tipo, estado)

    def factura_electronica(self, factura_id: int) -> Optional[DocumentoElectronico]:
        """La factura electrónica vigente: la aceptada, o la última si ninguna está aceptada."""
        docs = self._documentos.buscar(factura_id=factura_id, tipo=T.FACTURA)
        aceptadas = [d for d in docs if d.estado == E.ACEPTADO]
        return (aceptadas or docs or [None])[0]

    def tiene_factura_aceptada(self, factura_id: int) -> bool:
        doc = self.factura_electronica(factura_id)
        return doc is not None and doc.estado == E.ACEPTADO

    def notas_credito(self, factura_id: int) -> list[DocumentoElectronico]:
        return self._documentos.buscar(factura_id=factura_id, tipo=T.NOTA_CREDITO)

    # ------------------------------------------------------------------ emisión

    def emitir(self, factura_id: int, usuario: Usuario) -> DocumentoElectronico:
        """Genera la factura electrónica de una factura y la envía al proveedor (RN-20)."""
        with self._lock:
            factura = self._facturacion.obtener(factura_id)
            if factura.estado == EstadoFactura.ANULADA:
                raise ReglaNegocio("La factura está anulada: no se emite factura electrónica.")
            existente = self.factura_electronica(factura_id)
            if existente is not None:
                if existente.estado == E.RECHAZADO:
                    raise Conflicto("La factura electrónica fue rechazada: corrija los datos y use «Reintentar».")
                raise Conflicto("La factura ya tiene factura electrónica.")
            doc = DocumentoElectronico(
                factura_id=factura.id,
                tipo=T.FACTURA,
                prefijo=self._config.dian_prefijo,
                consecutivo=self._siguiente_consecutivo(T.FACTURA),
            )
            self._llenar_factura(doc, factura)
            return self._enviar(doc, factura, nuevo=True)

    def reintentar(self, documento_id: int, usuario: Usuario) -> DocumentoElectronico:
        """Vuelve a generar y enviar una factura electrónica rechazada, conservando su numeración."""
        with self._lock:
            doc = self.obtener(documento_id)
            if doc.tipo != T.FACTURA:
                raise ReglaNegocio("Solo se reintentan las facturas electrónicas.")
            if doc.estado != E.RECHAZADO:
                raise ReglaNegocio("Solo se reintentan los documentos rechazados.")
            factura = self._facturacion.obtener(doc.factura_id)
            if factura.estado == EstadoFactura.ANULADA:
                raise ReglaNegocio("La factura está anulada: no se reintenta.")
            self._llenar_factura(doc, factura)
            return self._enviar(doc, factura, nuevo=False)

    # ------------------------------------------------------------------ notas crédito

    def emitir_nota_credito(
        self,
        factura_id: int,
        concepto: ConceptoNotaCredito,
        usuario: Usuario,
        motivo: str = "",
        glosa_id: Optional[int] = None,
    ) -> DocumentoElectronico:
        with self._lock:
            return self._nota_credito(factura_id, concepto, motivo, glosa_id)

    def anular_con_nota_credito(self, factura_id: int, motivo: str, usuario: Usuario) -> Factura:
        """Anula una factura que ya tiene factura electrónica aceptada: primero la nota crédito, luego la anulación."""
        motivo = (motivo or "").strip()
        if not motivo:
            raise ReglaNegocio("Indique el motivo de la anulación.")
        with self._lock:
            factura = self._facturacion.obtener(factura_id)
            if factura.pagos or factura.radicada:
                raise ReglaNegocio("La factura ya tiene pagos o fue radicada: no se puede anular.")
            nota = self._nota_credito(factura_id, ConceptoNotaCredito.ANULACION, motivo, None)
            if nota.estado != E.ACEPTADO:
                raise ReglaNegocio(f"No se anuló: la nota crédito fue rechazada. {nota.mensaje_respuesta}")
        return self._facturacion.anular(factura_id, f"{motivo} (nota crédito {nota.numero})", desde_nota_credito=True)

    # ------------------------------------------------------------------ internos

    def _siguiente_consecutivo(self, tipo: T) -> int:
        existentes = [d.consecutivo for d in self._documentos.buscar(tipo=tipo)]
        if existentes:
            return max(existentes) + 1
        return self._config.dian_rango_desde if tipo == T.FACTURA else 1

    def _adquirente(self, factura: Factura) -> dict:
        """A quién se le factura: al pagador por lo que le corresponde o, si no hay pagador, al paciente."""
        if factura.valor_pagador > 0 and factura.pagador_id is not None:
            pagador = self._convenios.obtener_pagador(factura.pagador_id, incluir_inactivo=True)
            documento, dv = nit_sin_dv(pagador.nit)
            return dict(
                adquirente_tipo_documento=TIPO_NIT, adquirente_documento=documento, adquirente_dv=dv,
                adquirente_nombre=pagador.nombre, adquirente_es_pagador=True, valor=factura.valor_pagador,
            )
        paciente = self._pacientes.obtener_por_id(factura.paciente_id)
        if paciente is None:
            raise NoEncontrado("No se encontró el paciente de la factura.")
        return dict(
            adquirente_tipo_documento=TIPO_DOCUMENTO_DIAN.get(paciente.tipo_documento, "13"),
            adquirente_documento=paciente.numero_documento, adquirente_dv="",
            adquirente_nombre=paciente.nombre_completo, adquirente_es_pagador=False, valor=factura.valor_paciente,
        )

    def _lineas(self, factura: Factura) -> list[LineaXml]:
        por_id = {r.id: r for r in self._realizados.obtener_por_ingreso(factura.ingreso_id)}
        lineas = []
        for n, linea in enumerate(factura.lineas, start=1):
            realizado = por_id.get(linea.procedimiento_realizado_id)
            lineas.append(
                LineaXml(n, (realizado.cups if realizado and realizado.cups else linea.codigo), linea.descripcion,
                         linea.cantidad, linea.valor_unitario, linea.subtotal)
            )
        return lineas

    def _datos_xml(self, doc: DocumentoElectronico, factura: Factura, lineas: list[LineaXml], **extra) -> DatosXml:
        paciente = self._pacientes.obtener_por_id(factura.paciente_id)
        emisor, dv = nit_sin_dv(self._config.ips_nit)
        return DatosXml(
            documento=doc, lineas=lineas, emisor_nombre=self._config.ips_nombre, emisor_nit=emisor, emisor_dv=dv,
            codigo_habilitacion=self._config.ips_codigo_habilitacion,
            usuario_documento=paciente.numero_documento if paciente else "",
            usuario_nombre=paciente.nombre_completo if paciente else "",
            valor_paciente=factura.valor_paciente if doc.adquirente_es_pagador else 0,
            numero_autorizacion="", **extra,
        )

    def _llenar_factura(self, doc: DocumentoElectronico, factura: Factura) -> None:
        for campo, valor in self._adquirente(factura).items():
            setattr(doc, campo, valor)
        doc.fecha = ahora_local(self._config.zona_horaria)
        doc.valor_bruto = factura.total
        nit, _ = nit_sin_dv(self._config.ips_nit)
        doc.cufe = calcular_cufe(
            doc.numero, doc.fecha, doc.valor_bruto, doc.valor, nit, doc.adquirente_tipo_documento,
            doc.adquirente_documento, self._config.dian_clave_tecnica, self._config.dian_ambiente, self._config.zona_horaria,
        )
        doc.qr = generar_qr(doc, nit, self._config.dian_ambiente, self._config.zona_horaria)
        doc.xml = generar_xml(self._datos_xml(doc, factura, self._lineas(factura)), self._config)

    def _enviar(self, doc: DocumentoElectronico, factura: Optional[Factura], nuevo: bool) -> DocumentoElectronico:
        ahora = ahora_local(self._config.zona_horaria)
        doc.eventos.append(EventoDocumento(ahora, E.GENERADO, f"Documento {doc.numero} generado con su CUFE y su XML."))
        respuesta = self._proveedor.enviar(doc)
        doc.intentos += 1
        doc.estado = E.ACEPTADO if respuesta.aceptado else E.RECHAZADO
        doc.codigo_respuesta = respuesta.codigo
        doc.mensaje_respuesta = respuesta.mensaje
        doc.eventos.append(EventoDocumento(ahora_local(self._config.zona_horaria), doc.estado, respuesta.mensaje))
        guardado = self._documentos.agregar(doc) if nuevo else self._documentos.actualizar(doc)
        auditar(self._auditoria, "DocumentoElectronico", "EMISION" if nuevo else "REINTENTO", guardado.id)
        return guardado

    def _nota_credito(
        self, factura_id: int, concepto: ConceptoNotaCredito, motivo: str, glosa_id: Optional[int]
    ) -> DocumentoElectronico:
        factura = self._facturacion.obtener(factura_id)
        referencia = self.factura_electronica(factura_id)
        if referencia is None or referencia.estado != E.ACEPTADO:
            raise ReglaNegocio("La nota crédito solo aplica a una factura con factura electrónica aceptada.")
        previas = [n for n in self.notas_credito(factura_id) if n.estado != E.RECHAZADO]
        disponible = referencia.valor - sum(n.valor for n in previas)
        motivo = (motivo or "").strip()
        lineas = self._lineas(factura)
        if concepto == ConceptoNotaCredito.GLOSA:
            glosa = next((g for g in factura.glosas if g.id == glosa_id), None)
            if glosa is None:
                raise NoEncontrado("La glosa no existe en esta factura.")
            if glosa.estado != EstadoGlosa.ACEPTADA:
                raise ReglaNegocio("Solo se emite nota crédito por glosas aceptadas.")
            if any(n.glosa_id == glosa.id for n in previas):
                raise Conflicto("Esa glosa ya tiene nota crédito.")
            valor, valor_bruto = glosa.valor, glosa.valor
            motivo = motivo or f"Glosa aceptada: {glosa.motivo}"[:200]
            lineas = [LineaXml(1, "GLOSA", f"Glosa aceptada ({glosa.concepto.value.lower()})", 1, glosa.valor, glosa.valor)]
        else:
            if not motivo:
                raise ReglaNegocio("Indique el motivo de la nota crédito.")
            if previas and any(n.concepto == ConceptoNotaCredito.ANULACION for n in previas):
                raise Conflicto("La factura ya tiene una nota crédito de anulación.")
            valor, valor_bruto = disponible, factura.total
        if valor <= 0 or valor > disponible:
            raise ReglaNegocio("La nota crédito excede el valor pendiente de la factura electrónica.")
        doc = DocumentoElectronico(
            factura_id=factura.id, tipo=T.NOTA_CREDITO, prefijo=PREFIJO_NOTA,
            consecutivo=self._siguiente_consecutivo(T.NOTA_CREDITO), documento_referencia_id=referencia.id,
            concepto=concepto, motivo=motivo, glosa_id=glosa_id if concepto == ConceptoNotaCredito.GLOSA else None,
            adquirente_tipo_documento=referencia.adquirente_tipo_documento, adquirente_documento=referencia.adquirente_documento,
            adquirente_dv=referencia.adquirente_dv, adquirente_nombre=referencia.adquirente_nombre,
            adquirente_es_pagador=referencia.adquirente_es_pagador, valor=valor, valor_bruto=valor_bruto,
            fecha=ahora_local(self._config.zona_horaria),
        )
        nit, _ = nit_sin_dv(self._config.ips_nit)
        doc.cufe = calcular_cude(
            doc.numero, doc.fecha, doc.valor_bruto, doc.valor, nit, doc.adquirente_documento,
            self._config.dian_pin_software, self._config.dian_ambiente, self._config.zona_horaria,
        )
        doc.qr = generar_qr(doc, nit, self._config.dian_ambiente, self._config.zona_horaria)
        doc.xml = generar_xml(
            self._datos_xml(
                doc, factura, lineas, factura_numero=referencia.numero, factura_cufe=referencia.cufe,
                factura_fecha=referencia.fecha.strftime("%Y-%m-%d"),
            ),
            self._config,
        )
        return self._enviar(doc, None, nuevo=True)
