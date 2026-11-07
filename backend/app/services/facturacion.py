"""Facturación de los procedimientos de un ingreso y cobro al paciente (RF-18, RF-19)."""
from __future__ import annotations

import dataclasses
import threading
from typing import Optional

from app.config import Configuracion
from app.core.tiempo import ahora_local
from app.domain.excepciones import NoEncontrado, ReglaNegocio
from app.domain.modelos import (
    EstadoDocumentoElectronico,
    EstadoFactura,
    Factura,
    LineaFactura,
    MetodoPago,
    OrigenPago,
    PagoFactura,
    TipoDocumentoElectronico,
    Usuario,
)
from app.repositories.interfaces import (
    IDocumentoElectronicoRepository,
    IFacturaRepository,
    IIngresoRepository,
    IProcedimientoRealizadoRepository,
)
from app.services.caja import CajaService
from app.services.convenios import ConvenioService, repartir_total


class FacturacionService:
    def __init__(
        self,
        facturas: IFacturaRepository,
        realizados: IProcedimientoRealizadoRepository,
        ingresos: IIngresoRepository,
        config: Configuracion,
        convenios: ConvenioService,
        cajas: CajaService,
        documentos: IDocumentoElectronicoRepository,
    ) -> None:
        self._cajas = cajas
        self._documentos = documentos
        self._convenios = convenios
        self._facturas = facturas
        self._realizados = realizados
        self._ingresos = ingresos
        self._config = config
        self._lock = threading.Lock()

    @property
    def bloqueo(self) -> threading.Lock:
        """Candado compartido con la cartera: ambos modifican las mismas facturas."""
        return self._lock

    def facturar(
        self, ingreso_id: int, usuario: Usuario, procedimiento_ids: Optional[list[int]] = None
    ) -> Factura:
        """Genera una factura con los procedimientos pendientes (todos, o los indicados).

        RN-12: un procedimiento se factura una sola vez; los anulados no se cobran.
        """
        with self._lock:
            ingreso = self._ingresos.obtener_por_id(ingreso_id)
            if ingreso is None:
                raise NoEncontrado("El ingreso no existe.")
            todos = self._realizados.obtener_por_ingreso(ingreso_id)
            pendientes = {p.id: p for p in todos if not p.anulado and p.factura_id is None}

            if procedimiento_ids is None:
                elegidos = list(pendientes.values())
            else:
                if len(set(procedimiento_ids)) != len(procedimiento_ids):
                    raise ReglaNegocio("Hay procedimientos repetidos en la solicitud.")
                elegidos = []
                for pid in procedimiento_ids:
                    if pid not in pendientes:
                        raise ReglaNegocio(
                            f"El procedimiento {pid} no está pendiente de facturar en este ingreso."
                        )
                    elegidos.append(pendientes[pid])
            if not elegidos:
                raise ReglaNegocio("No hay procedimientos pendientes de facturar en este ingreso.")

            convenio = self._convenios.obtener_convenio(ingreso.convenio_id) if ingreso.convenio_id else None
            pagador = (
                self._convenios.obtener_pagador(convenio.pagador_id, incluir_inactivo=True) if convenio else None
            )
            total = sum(p.subtotal for p in elegidos)
            # La cuota moderadora se cobra una sola vez por ingreso, en la primera factura vigente.
            if convenio is not None and any(
                f.estado != EstadoFactura.ANULADA for f in self._facturas.buscar(ingreso_id=ingreso.id)
            ):
                convenio_a_repartir = dataclasses.replace(convenio, cuota_moderadora=0)
            else:
                convenio_a_repartir = convenio
            valor_paciente, valor_pagador = repartir_total(total, convenio_a_repartir)

            factura = self._facturas.agregar(
                Factura(
                    ingreso_id=ingreso.id,
                    paciente_id=ingreso.paciente_id,
                    fecha=ahora_local(self._config.zona_horaria),
                    emitida_por_id=usuario.id,
                    pagador_id=pagador.id if pagador else None,
                    pagador_codigo=pagador.codigo if pagador else "",
                    pagador_nombre=pagador.nombre if pagador else "",
                    convenio_id=convenio.id if convenio else None,
                    convenio_nombre=convenio.nombre if convenio else "",
                    valor_paciente=valor_paciente,
                    valor_pagador=valor_pagador,
                    lineas=[
                        LineaFactura(
                            procedimiento_realizado_id=p.id,
                            codigo=p.codigo,
                            descripcion=p.nombre,
                            cantidad=p.cantidad,
                            valor_unitario=p.valor_unitario,
                        )
                        for p in elegidos
                    ],
                )
            )
            for p in elegidos:
                p.factura_id = factura.id
                self._realizados.actualizar(p)
            return factura

    def obtener(self, factura_id: int) -> Factura:
        factura = self._facturas.obtener_por_id(factura_id)
        if factura is None:
            raise NoEncontrado("La factura no existe.")
        return factura

    def buscar(
        self,
        estado: Optional[EstadoFactura] = None,
        paciente_id: Optional[int] = None,
        ingreso_id: Optional[int] = None,
    ) -> list[Factura]:
        return self._facturas.buscar(estado, paciente_id, ingreso_id)

    def pagar(self, factura_id: int, metodo: MetodoPago, usuario: Optional[Usuario] = None) -> Factura:
        """Registra el pago de lo que debe el paciente (todo, si es particular; el copago, si hay convenio)."""
        with self._lock:
            factura = self.obtener(factura_id)
            if factura.estado != EstadoFactura.EMITIDA:
                raise ReglaNegocio(f"La factura está {factura.estado.value.lower()}: solo se pagan las emitidas.")
            if factura.saldo_paciente <= 0:
                raise ReglaNegocio("El paciente no tiene saldo pendiente en esta factura.")
            caja = self._cajas.caja_para_cobrar(usuario)  # RN-23
            ahora = ahora_local(self._config.zona_horaria)
            factura.pagos.append(
                PagoFactura(
                    origen=OrigenPago.PACIENTE,
                    metodo=metodo,
                    valor=factura.saldo_paciente,
                    fecha=ahora,
                    registrado_por_id=usuario.id if usuario else 0,
                    recibo_numero=self._cajas.nuevo_recibo(),
                    caja_id=caja.id if caja else None,
                )
            )
            factura.metodo_pago = metodo
            if factura.saldada():
                factura.estado = EstadoFactura.PAGADA
                factura.fecha_pago = ahora
            return self._facturas.actualizar(factura)

    def anular(self, factura_id: int, motivo: str, desde_nota_credito: bool = False) -> Factura:
        """Anula una factura emitida y deja sus procedimientos otra vez pendientes (RN-13).

        Una factura pagada, con algún pago registrado o ya radicada al pagador no se anula
        (RN-17). Con factura electrónica aceptada se anula con nota crédito (RN-21).
        """
        motivo = (motivo or "").strip()
        if not motivo:
            raise ReglaNegocio("Indique el motivo de la anulación.")
        with self._lock:
            factura = self.obtener(factura_id)
            if factura.estado != EstadoFactura.EMITIDA:
                raise ReglaNegocio(f"La factura está {factura.estado.value.lower()}: solo se anulan las emitidas.")
            if factura.pagos:
                raise ReglaNegocio("La factura ya tiene pagos registrados: no se puede anular.")
            if not desde_nota_credito and any(
                d.estado == EstadoDocumentoElectronico.ACEPTADO
                for d in self._documentos.buscar(factura_id=factura.id, tipo=TipoDocumentoElectronico.FACTURA)
            ):
                raise ReglaNegocio(
                    "La factura tiene factura electrónica aceptada: se anula con una nota crédito."
                )
            if factura.radicada:
                raise ReglaNegocio("La factura ya fue radicada al pagador: no se puede anular.")
            factura.estado = EstadoFactura.ANULADA
            factura.motivo_anulacion = motivo
            factura = self._facturas.actualizar(factura)
            for p in self._realizados.obtener_por_ingreso(factura.ingreso_id):
                if p.factura_id == factura.id:
                    p.factura_id = None
                    self._realizados.actualizar(p)
            return factura
