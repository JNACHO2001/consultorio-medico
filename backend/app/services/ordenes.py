"""Órdenes de apoyo diagnóstico y sus resultados (RF-23, RF-24)."""
from __future__ import annotations

import threading
from typing import Optional

from app.config import Configuracion
from app.core.auditoria import auditar
from app.core.tiempo import ahora_local
from app.domain.excepciones import NoEncontrado, Prohibido, ReglaNegocio
from app.domain.modelos import (
    AreaApoyo,
    EstadoIngreso,
    EstadoOrden,
    OrdenClinica,
    PrioridadOrden,
    ResultadoValor,
    Rol,
    Usuario,
)
from app.repositories.interfaces import IAuditoriaRepository, IOrdenRepository
from app.services.catalogo import CatalogoService
from app.services.ingreso import CANTIDAD_MAXIMA, IngresoService

MAX_VALORES = 40


class OrdenService:
    def __init__(
        self,
        ordenes: IOrdenRepository,
        ingresos: IngresoService,
        catalogo: CatalogoService,
        auditoria: IAuditoriaRepository,
        config: Configuracion,
    ) -> None:
        self._ordenes = ordenes
        self._ingresos = ingresos
        self._catalogo = catalogo
        self._auditoria = auditoria
        self._config = config
        self._lock = threading.Lock()

    def obtener(self, orden_id: int) -> OrdenClinica:
        orden = self._ordenes.obtener_por_id(orden_id)
        if orden is None:
            raise NoEncontrado("La orden no existe.")
        return orden

    def buscar(
        self,
        estado: Optional[EstadoOrden] = None,
        ingreso_id: Optional[int] = None,
        paciente_id: Optional[int] = None,
        area: Optional[AreaApoyo] = None,
        medico_id: Optional[int] = None,
    ) -> list[OrdenClinica]:
        return self._ordenes.buscar(estado, ingreso_id, paciente_id, area, medico_id)

    def crear(
        self,
        ingreso_id: int,
        medico: Usuario,
        procedimiento_id: int,
        cantidad: int = 1,
        prioridad: PrioridadOrden = PrioridadOrden.RUTINA,
        indicacion: str = "",
    ) -> OrdenClinica:
        """El médico tratante ordena un servicio de apoyo diagnóstico a su paciente ingresado."""
        if not isinstance(cantidad, int) or not 1 <= cantidad <= CANTIDAD_MAXIMA:
            raise ReglaNegocio(f"La cantidad debe estar entre 1 y {CANTIDAD_MAXIMA}.")
        ingreso = self._ingresos.obtener(ingreso_id)
        if ingreso.medico_id != medico.id:
            raise Prohibido("El ingreso pertenece a otro médico.")
        if ingreso.estado != EstadoIngreso.ABIERTO:
            raise ReglaNegocio("El ingreso ya tiene egreso: no se pueden generar órdenes.")
        item = self._catalogo.obtener(procedimiento_id)
        if item.area_apoyo == AreaApoyo.NINGUNA:
            raise ReglaNegocio(f"{item.nombre} no es un servicio de apoyo diagnóstico: regístrelo como procedimiento.")
        with self._lock:
            return self._ordenes.agregar(
                OrdenClinica(
                    ingreso_id=ingreso.id,
                    paciente_id=ingreso.paciente_id,
                    medico_id=medico.id,
                    procedimiento_id=item.id,
                    codigo=item.codigo,
                    nombre=item.nombre,
                    cups=item.cups,
                    area=item.area_apoyo,
                    cantidad=cantidad,
                    prioridad=prioridad,
                    indicacion=(indicacion or "").strip(),
                    fecha=ahora_local(self._config.zona_horaria),
                )
            )

    def anular(self, orden_id: int, medico: Usuario, motivo: str) -> OrdenClinica:
        motivo = (motivo or "").strip()
        if not motivo:
            raise ReglaNegocio("Indique el motivo de la anulación.")
        with self._lock:
            orden = self.obtener(orden_id)
            if orden.medico_id != medico.id:
                raise Prohibido("La orden pertenece a otro médico.")
            if orden.estado != EstadoOrden.SOLICITADA:
                raise ReglaNegocio("Solo se anulan las órdenes que aún no tienen resultado.")
            orden.estado = EstadoOrden.ANULADA
            orden.motivo_anulacion = motivo
            return self._ordenes.actualizar(orden)

    def registrar_resultado(
        self,
        orden_id: int,
        usuario: Usuario,
        valores: list[ResultadoValor],
        interpretacion: str = "",
    ) -> OrdenClinica:
        """Apoyo diagnóstico registra el resultado; el servicio se carga a la cuenta del ingreso (RN-21)."""
        if usuario.rol not in (Rol.LABORATORIO, Rol.MEDICO):
            raise Prohibido("Solo apoyo diagnóstico o el médico tratante registran resultados.")
        valores = [v for v in valores if (v.parametro or "").strip() or (v.valor or "").strip()]
        interpretacion = (interpretacion or "").strip()
        if not valores and not interpretacion:
            raise ReglaNegocio("Registre al menos un valor o la interpretación del resultado.")
        if len(valores) > MAX_VALORES:
            raise ReglaNegocio(f"Un resultado admite hasta {MAX_VALORES} valores.")
        for v in valores:
            if not (v.parametro or "").strip() or not (v.valor or "").strip():
                raise ReglaNegocio("Cada línea del resultado necesita parámetro y valor.")
            if v.ref_min is not None and v.ref_max is not None and v.ref_min > v.ref_max:
                raise ReglaNegocio(f"El rango de referencia de {v.parametro} está invertido.")
        with self._lock:
            orden = self.obtener(orden_id)
            if usuario.rol == Rol.MEDICO and orden.medico_id != usuario.id:
                raise Prohibido("La orden pertenece a otro médico.")
            if orden.estado != EstadoOrden.SOLICITADA:
                raise ReglaNegocio("La orden ya tiene resultado o está anulada.")
            cargo = self._ingresos.cargar_servicio_de_apoyo(
                orden.ingreso_id, orden.procedimiento_id, orden.cantidad, f"Orden #{orden.id}"
            )
            orden.valores = [
                ResultadoValor(v.parametro.strip(), v.valor.strip(), (v.unidad or "").strip(), v.ref_min, v.ref_max)
                for v in valores
            ]
            orden.interpretacion = interpretacion
            orden.estado = EstadoOrden.REALIZADA
            orden.fecha_resultado = ahora_local(self._config.zona_horaria)
            orden.registrado_por_id = usuario.id
            orden.realizado_id = cargo.id
            actualizada = self._ordenes.actualizar(orden)
        auditar(self._auditoria, "Orden", "RESULTADO", actualizada.id)
        return actualizada
