"""Borrador del RIPS (Registro Individual de Prestación de Servicios de Salud) (RF-22).

Agrupa por factura al usuario atendido y sus servicios (consultas, procedimientos y otros
servicios) y señala qué datos faltan antes de reportarlo. Es un borrador en JSON con la
estructura general del RIPS: la validación oficial ante el Ministerio de Salud queda fuera
del alcance del prototipo.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Optional

from app.config import Configuracion
from app.core.auditoria import auditar
from app.domain.excepciones import ReglaNegocio
from app.domain.modelos import EstadoDocumentoElectronico, EstadoFactura, Factura, TipoDocumentoElectronico, TipoServicio
from app.repositories.interfaces import (
    IAuditoriaRepository,
    IDocumentoElectronicoRepository,
    IFacturaRepository,
    IIngresoRepository,
    IPacienteRepository,
    IProcedimientoRealizadoRepository,
)
from app.core.tiempo import ahora_local

DIAS_MAXIMOS = 366
_GRUPOS = {
    TipoServicio.CONSULTA: "consultas",
    TipoServicio.PROCEDIMIENTO: "procedimientos",
    TipoServicio.OTRO_SERVICIO: "otrosServicios",
}


class RipsService:
    def __init__(
        self,
        facturas: IFacturaRepository,
        ingresos: IIngresoRepository,
        realizados: IProcedimientoRealizadoRepository,
        pacientes: IPacienteRepository,
        auditoria: IAuditoriaRepository,
        config: Configuracion,
        documentos: IDocumentoElectronicoRepository,
    ) -> None:
        self._documentos = documentos
        self._facturas = facturas
        self._ingresos = ingresos
        self._realizados = realizados
        self._pacientes = pacientes
        self._auditoria = auditoria
        self._config = config

    def generar(self, desde: date, hasta: date, pagador_id: Optional[int] = None) -> dict[str, Any]:
        if desde > hasta:
            raise ReglaNegocio("La fecha inicial no puede ser posterior a la final.")
        if (hasta - desde).days > DIAS_MAXIMOS:
            raise ReglaNegocio(f"El periodo no puede pasar de {DIAS_MAXIMOS} días.")

        incluidas = [
            f
            for f in self._facturas.buscar()
            if f.estado != EstadoFactura.ANULADA
            and f.valor_pagador > 0
            and f.fecha is not None
            and desde <= f.fecha.date() <= hasta
            and (pagador_id is None or f.pagador_id == pagador_id)
        ]
        incluidas.sort(key=lambda f: f.id)

        facturas_rips: list[dict[str, Any]] = []
        inconsistencias: list[dict[str, str]] = []
        for factura in incluidas:
            registro, problemas = self._factura(factura)
            facturas_rips.append(registro)
            inconsistencias.extend(problemas)

        auditar(self._auditoria, "Rips", "GENERACION")
        return {
            "borrador": True,
            "prestador": {
                "nombre": self._config.ips_nombre,
                "nit": self._config.ips_nit,
                "codigoHabilitacion": self._config.ips_codigo_habilitacion,
            },
            "periodo": {"desde": desde.isoformat(), "hasta": hasta.isoformat()},
            "generado": ahora_local(self._config.zona_horaria).isoformat(),
            "resumen": {
                "facturas": len(facturas_rips),
                "valorFacturado": sum(f["valorPagador"] for f in facturas_rips),
                "errores": sum(1 for i in inconsistencias if i["nivel"] == "ERROR"),
                "avisos": sum(1 for i in inconsistencias if i["nivel"] == "AVISO"),
                "listoParaReportar": not any(i["nivel"] == "ERROR" for i in inconsistencias),
            },
            "facturas": facturas_rips,
            "inconsistencias": inconsistencias,
        }

    def _factura(self, factura: Factura) -> tuple[dict[str, Any], list[dict[str, str]]]:
        problemas: list[dict[str, str]] = []

        def problema(nivel: str, codigo: str, mensaje: str) -> None:
            problemas.append({"factura": factura.numero, "nivel": nivel, "codigo": codigo, "mensaje": mensaje})

        ingreso = self._ingresos.obtener_por_id(factura.ingreso_id)
        paciente = self._pacientes.obtener_por_id(factura.paciente_id)
        diagnostico = ingreso.diagnostico_principal if ingreso else ""
        if not diagnostico:
            problema("ERROR", "SIN_DIAGNOSTICO", "El ingreso no tiene diagnóstico principal CIE-10.")
        if not factura.radicada:
            problema("AVISO", "NO_RADICADA", "La factura aún no se ha radicado al pagador.")
        electronica = next(
            (
                d
                for d in self._documentos.buscar(factura_id=factura.id, tipo=TipoDocumentoElectronico.FACTURA)
                if d.estado == EstadoDocumentoElectronico.ACEPTADO
            ),
            None,
        )
        if electronica is None and self._config.dian_obligatoria:
            problema("AVISO", "SIN_FACTURA_ELECTRONICA", "La factura no tiene factura electrónica aceptada.")

        usuario: dict[str, Any] = {}
        if paciente is None:
            problema("ERROR", "USUARIO_INCOMPLETO", "No se encontró el paciente de la factura.")
        else:
            usuario = {
                "tipoDocumentoIdentificacion": paciente.tipo_documento,
                "numDocumentoIdentificacion": paciente.numero_documento,
                "fechaNacimiento": paciente.fecha_nacimiento.isoformat() if paciente.fecha_nacimiento else None,
                "codSexo": paciente.sexo or None,
            }
            if paciente.fecha_nacimiento is None or paciente.sexo not in ("M", "F"):
                problema("ERROR", "USUARIO_INCOMPLETO", "Al paciente le falta la fecha de nacimiento o el sexo.")

        por_id = {r.id: r for r in self._realizados.obtener_por_ingreso(factura.ingreso_id)}
        servicios: dict[str, list[dict[str, Any]]] = {g: [] for g in _GRUPOS.values()}
        for consecutivo, linea in enumerate(factura.lineas, start=1):
            realizado = por_id.get(linea.procedimiento_realizado_id)
            tipo = realizado.tipo_servicio if realizado else TipoServicio.PROCEDIMIENTO
            cups = realizado.cups if realizado else ""
            if not cups:
                problema("ERROR", "SIN_CUPS", f"El servicio {linea.codigo} no tiene código CUPS en el catálogo.")
            servicios[_GRUPOS[tipo]].append(
                {
                    "consecutivo": consecutivo,
                    "codServicio": cups or None,
                    "codigoInterno": linea.codigo,
                    "descripcion": linea.descripcion,
                    "fechaAtencion": (
                        realizado.fecha_hora.isoformat() if realizado and realizado.fecha_hora else None
                    ),
                    "codDiagnosticoPrincipal": diagnostico or None,
                    "cantidad": linea.cantidad,
                    "vrUnitario": linea.valor_unitario,
                    "vrServicio": linea.subtotal,
                }
            )

        registro = {
            "numFactura": electronica.numero if electronica else factura.numero,
            "cufe": electronica.cufe if electronica else None,
            "fechaFactura": factura.fecha.isoformat() if factura.fecha else None,
            "pagador": {"codigo": factura.pagador_codigo, "nombre": factura.pagador_nombre},
            "convenio": factura.convenio_nombre,
            "numAutorizacion": (ingreso.numero_autorizacion or None) if ingreso else None,
            "valorTotal": factura.total,
            "valorPaciente": factura.valor_paciente,
            "valorPagador": factura.valor_pagador,
            "usuario": usuario,
            "servicios": servicios,
        }
        return registro, problemas
