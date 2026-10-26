"""Ingreso del paciente, procedimientos y egreso (RF-15, RF-16)."""
from __future__ import annotations

import threading
from typing import Optional

from app.config import Configuracion
from app.core.tiempo import ahora_local
from app.domain.excepciones import Conflicto, NoEncontrado, Prohibido, ReglaNegocio
from app.domain.modelos import (
    EstadoIngreso,
    Ingreso,
    ProcedimientoRealizado,
    Rol,
    TipoIngreso,
    Usuario,
)
from app.repositories.interfaces import (
    IIngresoRepository,
    IPacienteRepository,
    IProcedimientoRealizadoRepository,
    IUsuarioRepository,
)
from app.services.catalogo import CatalogoService

CANTIDAD_MAXIMA = 99


class IngresoService:
    def __init__(
        self,
        ingresos: IIngresoRepository,
        realizados: IProcedimientoRealizadoRepository,
        catalogo: CatalogoService,
        pacientes: IPacienteRepository,
        usuarios: IUsuarioRepository,
        config: Configuracion,
    ) -> None:
        self._ingresos = ingresos
        self._realizados = realizados
        self._catalogo = catalogo
        self._pacientes = pacientes
        self._usuarios = usuarios
        self._config = config
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ ingreso

    def admitir(
        self, paciente_id: int, medico_id: int, tipo: TipoIngreso, motivo: str, usuario: Usuario
    ) -> Ingreso:
        """Abre el ingreso del paciente con un médico tratante (RN-08: solo uno abierto a la vez)."""
        motivo = (motivo or "").strip()
        if not motivo:
            raise ReglaNegocio("El motivo del ingreso es obligatorio.")
        if self._pacientes.obtener_por_id(paciente_id) is None:
            raise NoEncontrado("El paciente no existe.")
        medico = self._usuarios.obtener_por_id(medico_id)
        if medico is None or medico.rol != Rol.MEDICO:
            raise NoEncontrado("El médico no existe.")
        with self._lock:
            abierto = self._ingresos.obtener_abierto_por_paciente(paciente_id)
            if abierto is not None:
                raise Conflicto(
                    "El paciente ya tiene un ingreso abierto: debe darse el egreso antes de un nuevo ingreso.",
                    {"ingreso_abierto_id": abierto.id},
                )
            return self._ingresos.agregar(
                Ingreso(
                    paciente_id=paciente_id,
                    medico_id=medico_id,
                    tipo=tipo,
                    motivo=motivo,
                    fecha_ingreso=ahora_local(self._config.zona_horaria),
                    admitido_por_id=usuario.id,
                )
            )

    def obtener(self, ingreso_id: int) -> Ingreso:
        ingreso = self._ingresos.obtener_por_id(ingreso_id)
        if ingreso is None:
            raise NoEncontrado("El ingreso no existe.")
        return ingreso

    def buscar(
        self,
        estado: Optional[EstadoIngreso] = None,
        medico_id: Optional[int] = None,
        paciente_id: Optional[int] = None,
    ) -> list[Ingreso]:
        return self._ingresos.buscar(estado, medico_id, paciente_id)

    def dar_egreso(self, ingreso_id: int, medico: Usuario, resumen: str = "") -> Ingreso:
        """El médico tratante da de alta al paciente; se sigue pudiendo facturar lo pendiente."""
        with self._lock:
            ingreso = self._propio_abierto(ingreso_id, medico, "dar el egreso")
            ingreso.estado = EstadoIngreso.EGRESADO
            ingreso.fecha_egreso = ahora_local(self._config.zona_horaria)
            ingreso.resumen_egreso = (resumen or "").strip()
            return self._ingresos.actualizar(ingreso)

    # ------------------------------------------------------------ procedimientos

    def registrar_procedimiento(
        self,
        ingreso_id: int,
        medico: Usuario,
        procedimiento_id: int,
        cantidad: int = 1,
        observaciones: str = "",
    ) -> ProcedimientoRealizado:
        """Carga un procedimiento a la cuenta del ingreso y a la historia clínica (RN-09, RN-10)."""
        if not isinstance(cantidad, int) or not 1 <= cantidad <= CANTIDAD_MAXIMA:
            raise ReglaNegocio(f"La cantidad debe estar entre 1 y {CANTIDAD_MAXIMA}.")
        with self._lock:
            ingreso = self._propio_abierto(ingreso_id, medico, "registrar procedimientos")
            catalogo = self._catalogo.obtener(procedimiento_id)
            return self._realizados.agregar(
                ProcedimientoRealizado(
                    ingreso_id=ingreso.id,
                    paciente_id=ingreso.paciente_id,
                    medico_id=medico.id,
                    procedimiento_id=catalogo.id,
                    codigo=catalogo.codigo,
                    nombre=catalogo.nombre,
                    cantidad=cantidad,
                    valor_unitario=catalogo.tarifa,
                    fecha_hora=ahora_local(self._config.zona_horaria),
                    observaciones=(observaciones or "").strip(),
                )
            )

    def anular_procedimiento(
        self, ingreso_id: int, realizado_id: int, medico: Usuario, motivo: str
    ) -> ProcedimientoRealizado:
        """Corrige un registro equivocado. No se borra: queda marcado como anulado (RN-11)."""
        motivo = (motivo or "").strip()
        if not motivo:
            raise ReglaNegocio("Indique el motivo de la anulación.")
        with self._lock:
            self._propio_abierto(ingreso_id, medico, "anular procedimientos")
            realizado = self._realizados.obtener_por_id(realizado_id)
            if realizado is None or realizado.ingreso_id != ingreso_id:
                raise NoEncontrado("El procedimiento no existe en este ingreso.")
            if realizado.anulado:
                raise ReglaNegocio("El procedimiento ya está anulado.")
            if realizado.factura_id is not None:
                raise ReglaNegocio("El procedimiento ya fue facturado: anule primero la factura.")
            realizado.anulado = True
            realizado.motivo_anulacion = motivo
            return self._realizados.actualizar(realizado)

    def procedimientos_de_ingreso(self, ingreso_id: int) -> list[ProcedimientoRealizado]:
        return self._realizados.obtener_por_ingreso(ingreso_id)

    def procedimientos_de_ingresos(self, ingreso_ids: list[int]) -> list[ProcedimientoRealizado]:
        return self._realizados.obtener_por_ingresos(ingreso_ids) if ingreso_ids else []

    def historia_de_procedimientos(self, paciente_id: int) -> list[ProcedimientoRealizado]:
        if self._pacientes.obtener_por_id(paciente_id) is None:
            raise NoEncontrado("El paciente no existe.")
        return self._realizados.obtener_por_paciente(paciente_id)

    # ------------------------------------------------------------------ internos

    def _propio_abierto(self, ingreso_id: int, medico: Usuario, accion: str) -> Ingreso:
        ingreso = self.obtener(ingreso_id)
        if ingreso.medico_id != medico.id:
            raise Prohibido("El ingreso pertenece a otro médico.")
        if ingreso.estado != EstadoIngreso.ABIERTO:
            raise ReglaNegocio(f"El ingreso ya tiene egreso: no se puede {accion}.")
        return ingreso
