"""Consultas médicas e historia clínica (CU-07, CU-08; RF-07 y RF-08)."""
from __future__ import annotations

from typing import Optional

from app.config import Configuracion
from app.core.tiempo import ahora_local
from app.domain.excepciones import Conflicto, NoEncontrado, Prohibido, ReglaNegocio
from app.domain.modelos import Consulta, EstadoCita, NotaAclaratoria, Usuario
from app.repositories.interfaces import ICitaRepository, IConsultaRepository, IPacienteRepository

CAMPOS_CLINICOS = (
    "motivo",
    "antecedentes",
    "signos_vitales",
    "diagnostico",
    "tratamiento",
    "formula",
    "observaciones",
)


class ConsultaService:
    def __init__(
        self,
        consultas: IConsultaRepository,
        citas: ICitaRepository,
        pacientes: IPacienteRepository,
        config: Configuracion,
    ) -> None:
        self._consultas = consultas
        self._citas = citas
        self._pacientes = pacientes
        self._config = config

    def registrar_consulta(self, cita_id: int, medico: Usuario, **datos: str) -> Consulta:
        cita = self._citas.obtener_por_id(cita_id)
        if cita is None:
            raise NoEncontrado("La cita no existe.")
        if cita.medico_id != medico.id:
            raise Prohibido("La cita pertenece a otro médico.")
        if cita.estado != EstadoCita.PROGRAMADA:
            raise ReglaNegocio(f"La cita está {cita.estado.value.lower()}: solo se atienden citas programadas.")
        if self._consultas.obtener_por_cita(cita_id) is not None:
            raise Conflicto("La cita ya tiene una consulta registrada.")

        consulta = Consulta(
            cita_id=cita.id,
            paciente_id=cita.paciente_id,
            medico_id=medico.id,
            fecha_hora=ahora_local(self._config.zona_horaria),
        )
        self._aplicar_datos(consulta, datos)
        if not consulta.motivo:
            raise ReglaNegocio("El motivo de consulta es obligatorio.")
        return self._consultas.agregar(consulta)

    def actualizar_consulta(self, consulta_id: int, medico: Usuario, **datos: str) -> Consulta:
        consulta = self._obtener_propia(consulta_id, medico)
        if consulta.cerrada:
            raise ReglaNegocio("La consulta está cerrada: use una nota aclaratoria para corregirla (RN-04).")
        self._aplicar_datos(consulta, datos)
        if not consulta.motivo:
            raise ReglaNegocio("El motivo de consulta es obligatorio.")
        return self._consultas.actualizar(consulta)

    def cerrar_consulta(self, consulta_id: int, medico: Usuario) -> Consulta:
        consulta = self._obtener_propia(consulta_id, medico)
        if consulta.cerrada:
            raise ReglaNegocio("La consulta ya está cerrada.")
        faltantes = [c for c in ("motivo", "diagnostico", "tratamiento") if not getattr(consulta, c)]
        if faltantes:
            raise ReglaNegocio(f"Para cerrar la consulta complete: {', '.join(faltantes)}.")
        consulta.cerrada = True
        consulta = self._consultas.actualizar(consulta)
        self._citas.actualizar_estado(consulta.cita_id, EstadoCita.ATENDIDA)
        return consulta

    def agregar_nota(self, consulta_id: int, medico: Usuario, texto: str) -> Consulta:
        """Corrige una consulta cerrada sin alterarla (RN-04)."""
        consulta = self._obtener_propia(consulta_id, medico)
        if not consulta.cerrada:
            raise ReglaNegocio("La consulta sigue abierta: edítela directamente.")
        texto = (texto or "").strip()
        if not texto:
            raise ReglaNegocio("Escriba el texto de la nota aclaratoria.")
        self._consultas.agregar_nota(
            consulta_id,
            NotaAclaratoria(
                texto=texto, fecha=ahora_local(self._config.zona_horaria), autor_id=medico.id
            ),
        )
        return self._obtener(consulta_id)

    def consultar_historial(self, paciente_id: int) -> list[Consulta]:
        """Historia clínica del paciente, de la consulta más reciente a la más antigua (RF-08)."""
        if self._pacientes.obtener_por_id(paciente_id) is None:
            raise NoEncontrado("El paciente no existe.")
        return self._consultas.obtener_por_paciente(paciente_id)

    def obtener_consulta(self, consulta_id: int) -> Consulta:
        return self._obtener(consulta_id)

    def obtener_por_cita(self, cita_id: int, medico: Usuario) -> Consulta:
        """Consulta ya registrada para una cita del médico (NoEncontrado si aún no hay)."""
        cita = self._citas.obtener_por_id(cita_id)
        if cita is None:
            raise NoEncontrado("La cita no existe.")
        if cita.medico_id != medico.id:
            raise Prohibido("La cita pertenece a otro médico.")
        consulta = self._consultas.obtener_por_cita(cita_id)
        if consulta is None:
            raise NoEncontrado("La cita aún no tiene una consulta registrada.")
        return consulta

    # ------------------------------------------------------------------ internos

    def _obtener(self, consulta_id: int) -> Consulta:
        consulta = self._consultas.obtener_por_id(consulta_id)
        if consulta is None:
            raise NoEncontrado("La consulta no existe.")
        return consulta

    def _obtener_propia(self, consulta_id: int, medico: Usuario) -> Consulta:
        consulta = self._obtener(consulta_id)
        if consulta.medico_id != medico.id:
            raise Prohibido("La consulta pertenece a otro médico.")
        return consulta

    @staticmethod
    def _aplicar_datos(consulta: Consulta, datos: dict[str, Optional[str]]) -> None:
        for campo in CAMPOS_CLINICOS:
            if campo in datos and datos[campo] is not None:
                setattr(consulta, campo, datos[campo].strip())
