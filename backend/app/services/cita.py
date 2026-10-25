"""Agenda de citas (CU-04, CU-05, CU-06; RF-05 y RF-06)."""
from __future__ import annotations

import threading
from datetime import date, datetime, timedelta
from typing import Optional

from app.config import Configuracion
from app.core.tiempo import a_hora_local, ahora_local
from app.domain.excepciones import Conflicto, NoEncontrado, ReglaNegocio
from app.domain.modelos import Cita, EstadoCita, Paciente, Rol, Usuario
from app.repositories.interfaces import ICitaRepository, IPacienteRepository, IUsuarioRepository
from app.services.notificaciones import NotificacionService


class CitaService:
    def __init__(
        self,
        citas: ICitaRepository,
        pacientes: IPacienteRepository,
        usuarios: IUsuarioRepository,
        notificaciones: NotificacionService,
        config: Configuracion,
    ) -> None:
        self._citas = citas
        self._pacientes = pacientes
        self._usuarios = usuarios
        self._notificaciones = notificaciones
        self._config = config
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ consultas

    def consultar_horarios_libres(self, medico_id: int, fecha: date) -> list[datetime]:
        self._validar_medico(medico_id)
        ocupadas = {c.fecha_hora for c in self._citas.obtener_por_medico_y_fecha(medico_id, fecha)}
        ahora = ahora_local(self._config.zona_horaria)
        return [f for f in self._franjas(fecha) if f not in ocupadas and f > ahora]

    def consultar_agenda(
        self, medico_id: int, fecha: date, dias: int = 1
    ) -> list[tuple[Cita, Optional[Paciente]]]:
        """Agenda diaria (dias=1) o semanal (dias=7) de un médico (RF-06)."""
        if not 1 <= dias <= 7:
            raise ReglaNegocio("La agenda puede consultarse de 1 a 7 días.")
        self._validar_medico(medico_id)
        citas = self._citas.obtener_por_medico_y_fecha(medico_id, fecha, dias)
        pacientes = {p.id: p for p in self._pacientes.obtener_por_ids([c.paciente_id for c in citas])}
        return [(c, pacientes.get(c.paciente_id)) for c in citas]

    def obtener_cita(self, cita_id: int) -> Cita:
        cita = self._citas.obtener_por_id(cita_id)
        if cita is None:
            raise NoEncontrado("La cita no existe.")
        return cita

    # ------------------------------------------------------------------ comandos

    def agendar_cita(self, paciente_id: int, medico_id: int, fecha_hora: datetime) -> Cita:
        fecha_hora = a_hora_local(fecha_hora, self._config.zona_horaria)
        with self._lock:  # RN-02: verificar el cruce y guardar es una sola operación
            paciente = self._pacientes.obtener_por_id(paciente_id)
            if paciente is None:
                raise NoEncontrado("El paciente no existe.")
            self._validar_medico(medico_id)
            self._validar_franja(fecha_hora)
            self._exigir_horario_libre(medico_id, fecha_hora)
            cita = self._citas.agregar(
                Cita(paciente_id=paciente_id, medico_id=medico_id, fecha_hora=fecha_hora)
            )
        self._notificaciones.programar_recordatorio(cita, paciente)
        return cita

    def reprogramar_cita(self, cita_id: int, nueva_fecha_hora: datetime) -> Cita:
        nueva_fecha_hora = a_hora_local(nueva_fecha_hora, self._config.zona_horaria)
        with self._lock:
            cita = self.obtener_cita(cita_id)
            self._exigir_programada(cita)
            self._validar_franja(nueva_fecha_hora)
            self._exigir_horario_libre(cita.medico_id, nueva_fecha_hora, excluir_cita_id=cita.id)
            cita.fecha_hora = nueva_fecha_hora
            cita = self._citas.actualizar(cita)
        paciente = self._pacientes.obtener_por_id(cita.paciente_id)
        if paciente is not None:
            self._notificaciones.reprogramar_recordatorio(cita, paciente)
        return cita

    def cancelar_cita(self, cita_id: int, motivo: str) -> Cita:
        motivo = (motivo or "").strip()
        if not motivo:
            raise ReglaNegocio("Indique el motivo de la cancelación.")
        with self._lock:
            cita = self.obtener_cita(cita_id)
            self._exigir_programada(cita)
            self._citas.actualizar_estado(cita_id, EstadoCita.CANCELADA, motivo)  # RN-06
        self._notificaciones.cancelar_recordatorio(cita_id)
        return self.obtener_cita(cita_id)

    # ------------------------------------------------------------------ reglas internas

    def _franjas(self, fecha: date) -> list[datetime]:
        cfg = self._config
        actual = datetime.combine(fecha, cfg.jornada_inicio)
        fin = datetime.combine(fecha, cfg.jornada_fin)
        paso = timedelta(minutes=cfg.duracion_cita_min)
        franjas = []
        while actual + paso <= fin:
            franjas.append(actual)
            actual += paso
        return franjas

    def _validar_franja(self, fecha_hora: datetime) -> None:
        if fecha_hora not in self._franjas(fecha_hora.date()):
            cfg = self._config
            raise ReglaNegocio(
                f"La hora no corresponde a una franja de atención: citas de {cfg.duracion_cita_min} minutos "
                f"entre {cfg.jornada_inicio:%H:%M} y {cfg.jornada_fin:%H:%M}."
            )
        if fecha_hora <= ahora_local(self._config.zona_horaria):
            raise ReglaNegocio("No se puede agendar una cita en el pasado.")

    def _validar_medico(self, medico_id: int) -> Usuario:
        medico = self._usuarios.obtener_por_id(medico_id)
        if medico is None or medico.rol != Rol.MEDICO:
            raise NoEncontrado("El médico no existe.")
        return medico

    def _exigir_horario_libre(
        self, medico_id: int, fecha_hora: datetime, excluir_cita_id: Optional[int] = None
    ) -> None:
        if self._citas.existe_cruce(medico_id, fecha_hora, excluir_cita_id):
            libres = self.consultar_horarios_libres(medico_id, fecha_hora.date())
            raise Conflicto(
                "El horario ya está ocupado para ese médico.",
                {"horarios_libres": [h.isoformat() for h in libres]},
            )

    @staticmethod
    def _exigir_programada(cita: Cita) -> None:
        if cita.estado != EstadoCita.PROGRAMADA:
            raise ReglaNegocio(f"La cita está {cita.estado.value.lower()}: solo se pueden modificar citas programadas.")
