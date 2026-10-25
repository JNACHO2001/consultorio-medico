"""Recordatorios de cita por correo o SMS (CU-10, RF-10).

El envío real lo hace un servicio externo; en el prototipo se simula con
NotificadorSimulado, que solo registra el mensaje. Cambiarlo por un proveedor
real consiste en implementar INotificador.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Optional

from app.config import Configuracion
from app.domain.modelos import Cita, EstadoRecordatorio, Paciente, Recordatorio
from app.repositories.interfaces import IRecordatorioRepository

registro = logging.getLogger("consultorio.notificaciones")


class INotificador(ABC):
    @abstractmethod
    def enviar(self, destinatario: str, canal: str, mensaje: str) -> None: ...


class NotificadorSimulado(INotificador):
    """No envía nada: anota el mensaje en el log y en una lista (útil para demostrar y probar)."""

    def __init__(self) -> None:
        self.enviados: list[dict[str, str]] = []

    def enviar(self, destinatario: str, canal: str, mensaje: str) -> None:
        self.enviados.append({"destinatario": destinatario, "canal": canal, "mensaje": mensaje})
        registro.info("[%s simulado] a %s: %s", canal, destinatario, mensaje)


class NotificacionService:
    def __init__(
        self,
        recordatorios: IRecordatorioRepository,
        notificador: INotificador,
        config: Configuracion,
    ) -> None:
        self._recordatorios = recordatorios
        self._notificador = notificador
        self._config = config

    def programar_recordatorio(self, cita: Cita, paciente: Paciente) -> Optional[Recordatorio]:
        """Programa el aviso `recordatorio_horas` antes de la cita. Sin contacto no se programa."""
        if paciente.correo:
            canal, destinatario = "CORREO", paciente.correo
        elif paciente.telefono:
            canal, destinatario = "SMS", paciente.telefono
        else:
            return None
        return self._recordatorios.agregar(
            Recordatorio(
                cita_id=cita.id,
                destinatario=destinatario,
                canal=canal,
                fecha_envio=cita.fecha_hora - timedelta(hours=self._config.recordatorio_horas),
            )
        )

    def cancelar_recordatorio(self, cita_id: int) -> None:
        pendiente = self._recordatorios.obtener_por_cita(cita_id)
        if pendiente is not None:
            pendiente.estado = EstadoRecordatorio.CANCELADO
            self._recordatorios.actualizar(pendiente)

    def reprogramar_recordatorio(self, cita: Cita, paciente: Paciente) -> Optional[Recordatorio]:
        self.cancelar_recordatorio(cita.id)
        return self.programar_recordatorio(cita, paciente)

    def procesar_pendientes(self, ahora: datetime) -> list[Recordatorio]:
        """Envía los recordatorios cuya hora ya llegó. Devuelve los enviados."""
        enviados = []
        for pendiente in self._recordatorios.obtener_pendientes(ahora):
            self._notificador.enviar(
                pendiente.destinatario,
                pendiente.canal,
                "Recordatorio de cita en el consultorio Salud Integral.",
            )
            pendiente.estado = EstadoRecordatorio.ENVIADO
            enviados.append(self._recordatorios.actualizar(pendiente))
        return enviados

    def listar_recordatorios(self) -> list[Recordatorio]:
        return self._recordatorios.listar(incluir_inactivos=True)
