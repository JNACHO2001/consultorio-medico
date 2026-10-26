"""Facturación de los procedimientos de un ingreso (RF-18)."""
from __future__ import annotations

import threading
from typing import Optional

from app.config import Configuracion
from app.core.tiempo import ahora_local
from app.domain.excepciones import NoEncontrado, ReglaNegocio
from app.domain.modelos import EstadoFactura, Factura, LineaFactura, MetodoPago, Usuario
from app.repositories.interfaces import (
    IFacturaRepository,
    IIngresoRepository,
    IProcedimientoRealizadoRepository,
)


class FacturacionService:
    def __init__(
        self,
        facturas: IFacturaRepository,
        realizados: IProcedimientoRealizadoRepository,
        ingresos: IIngresoRepository,
        config: Configuracion,
    ) -> None:
        self._facturas = facturas
        self._realizados = realizados
        self._ingresos = ingresos
        self._config = config
        self._lock = threading.Lock()

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

            factura = self._facturas.agregar(
                Factura(
                    ingreso_id=ingreso.id,
                    paciente_id=ingreso.paciente_id,
                    fecha=ahora_local(self._config.zona_horaria),
                    emitida_por_id=usuario.id,
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

    def pagar(self, factura_id: int, metodo: MetodoPago) -> Factura:
        with self._lock:
            factura = self.obtener(factura_id)
            if factura.estado != EstadoFactura.EMITIDA:
                raise ReglaNegocio(f"La factura está {factura.estado.value.lower()}: solo se pagan las emitidas.")
            factura.estado = EstadoFactura.PAGADA
            factura.metodo_pago = metodo
            factura.fecha_pago = ahora_local(self._config.zona_horaria)
            return self._facturas.actualizar(factura)

    def anular(self, factura_id: int, motivo: str) -> Factura:
        """Anula una factura emitida y deja sus procedimientos otra vez pendientes (RN-13).

        Una factura pagada no se anula: requeriría una nota crédito, fuera del alcance.
        """
        motivo = (motivo or "").strip()
        if not motivo:
            raise ReglaNegocio("Indique el motivo de la anulación.")
        with self._lock:
            factura = self.obtener(factura_id)
            if factura.estado != EstadoFactura.EMITIDA:
                raise ReglaNegocio(f"La factura está {factura.estado.value.lower()}: solo se anulan las emitidas.")
            factura.estado = EstadoFactura.ANULADA
            factura.motivo_anulacion = motivo
            factura = self._facturas.actualizar(factura)
            for p in self._realizados.obtener_por_ingreso(factura.ingreso_id):
                if p.factura_id == factura.id:
                    p.factura_id = None
                    self._realizados.actualizar(p)
            return factura
