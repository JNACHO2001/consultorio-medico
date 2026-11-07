"""Ingreso del paciente, procedimientos y egreso (RF-15, RF-16)."""
from __future__ import annotations

import re
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
from app.services.convenios import ConvenioService, calcular_precio

CANTIDAD_MAXIMA = 99
_PATRON_CIE10 = re.compile(r"^[A-Z][0-9]{2}[0-9A-Z]?$")


class IngresoService:
    def __init__(
        self,
        ingresos: IIngresoRepository,
        realizados: IProcedimientoRealizadoRepository,
        catalogo: CatalogoService,
        pacientes: IPacienteRepository,
        usuarios: IUsuarioRepository,
        config: Configuracion,
        convenios: ConvenioService,
    ) -> None:
        self._convenios = convenios
        self._ingresos = ingresos
        self._realizados = realizados
        self._catalogo = catalogo
        self._pacientes = pacientes
        self._usuarios = usuarios
        self._config = config
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ ingreso

    def admitir(
        self,
        paciente_id: int,
        medico_id: int,
        tipo: TipoIngreso,
        motivo: str,
        usuario: Usuario,
        convenio_id: Optional[int] = None,
        numero_autorizacion: str = "",
    ) -> Ingreso:
        """Abre el ingreso del paciente con un médico tratante (RN-08: solo uno abierto a la vez).

        Sin convenio se admite como particular. Si el convenio exige autorización (RN-16),
        el número de autorización es obligatorio.
        """
        motivo = (motivo or "").strip()
        if not motivo:
            raise ReglaNegocio("El motivo del ingreso es obligatorio.")
        if self._pacientes.obtener_por_id(paciente_id) is None:
            raise NoEncontrado("El paciente no existe.")
        medico = self._usuarios.obtener_por_id(medico_id)
        if medico is None or medico.rol != Rol.MEDICO:
            raise NoEncontrado("El médico no existe.")
        convenio = (
            self._convenios.obtener_convenio(convenio_id, incluir_inactivo=False)
            if convenio_id is not None
            else self._convenios.particular()
        )
        numero_autorizacion = (numero_autorizacion or "").strip()
        if convenio.requiere_autorizacion and not numero_autorizacion:
            raise ReglaNegocio("Este convenio exige número de autorización para admitir al paciente.")
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
                    convenio_id=convenio.id,
                    numero_autorizacion=numero_autorizacion,
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
            convenio = (
                self._convenios.obtener_convenio(ingreso.convenio_id) if ingreso.convenio_id is not None else None
            )
            return self._realizados.agregar(
                ProcedimientoRealizado(
                    ingreso_id=ingreso.id,
                    paciente_id=ingreso.paciente_id,
                    medico_id=medico.id,
                    procedimiento_id=catalogo.id,
                    codigo=catalogo.codigo,
                    nombre=catalogo.nombre,
                    cups=catalogo.cups,
                    tipo_servicio=catalogo.tipo_servicio,
                    cantidad=cantidad,
                    valor_unitario=calcular_precio(catalogo.tarifa, convenio),
                    fecha_hora=ahora_local(self._config.zona_horaria),
                    observaciones=(observaciones or "").strip(),
                )
            )

    def registrar_diagnostico(self, ingreso_id: int, medico: Usuario, codigo_cie10: str) -> Ingreso:
        """El médico tratante fija el diagnóstico principal (CIE-10) que el RIPS necesita."""
        codigo = (codigo_cie10 or "").strip().upper()
        if not _PATRON_CIE10.match(codigo):
            raise ReglaNegocio("El diagnóstico debe ser un código CIE-10 sin punto, por ejemplo J00 o K297.")
        with self._lock:
            ingreso = self._propio_abierto(ingreso_id, medico, "registrar el diagnóstico")
            ingreso.diagnostico_principal = codigo
            return self._ingresos.actualizar(ingreso)

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
