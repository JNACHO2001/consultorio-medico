"""Interfaces del patrón Repository.

Los servicios dependen únicamente de estas abstracciones (ver
docs/uml/02b_clases_repository.puml). Cambiar el almacenamiento (por ejemplo,
de una lista en memoria a una base de datos SQL) solo exige escribir nuevas
implementaciones de estas interfaces.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date, datetime
from typing import Generic, Optional, TypeVar

from app.domain.modelos import (
    Cita,
    Consulta,
    EstadoCita,
    NotaAclaratoria,
    Paciente,
    Recordatorio,
    RegistroAuditoria,
    Usuario,
)
from app.domain.modelos import Entidad

T = TypeVar("T", bound=Entidad)


class IRepository(ABC, Generic[T]):
    """Operaciones comunes. `desactivar` es un borrado lógico (RNF-11)."""

    @abstractmethod
    def agregar(self, entidad: T) -> T: ...

    @abstractmethod
    def obtener_por_id(self, id: int) -> Optional[T]: ...

    @abstractmethod
    def actualizar(self, entidad: T) -> T: ...

    @abstractmethod
    def desactivar(self, id: int) -> None: ...

    @abstractmethod
    def listar(self, incluir_inactivos: bool = False) -> list[T]: ...


class IPacienteRepository(IRepository[Paciente]):
    @abstractmethod
    def obtener_por_documento(self, tipo: str, numero: str) -> Optional[Paciente]: ...

    @abstractmethod
    def buscar(self, texto: str, limite: int = 50) -> list[Paciente]: ...

    @abstractmethod
    def obtener_por_ids(self, ids: list[int]) -> list[Paciente]: ...


class ICitaRepository(IRepository[Cita]):
    @abstractmethod
    def obtener_por_medico_y_fecha(
        self, medico_id: int, fecha: date, dias: int = 1, incluir_canceladas: bool = False
    ) -> list[Cita]: ...

    @abstractmethod
    def existe_cruce(
        self, medico_id: int, fecha_hora: datetime, excluir_cita_id: Optional[int] = None
    ) -> bool: ...

    @abstractmethod
    def actualizar_estado(
        self, cita_id: int, estado: EstadoCita, motivo_cancelacion: Optional[str] = None
    ) -> None: ...


class IConsultaRepository(IRepository[Consulta]):
    @abstractmethod
    def obtener_por_paciente(self, paciente_id: int) -> list[Consulta]:
        """Historial del paciente, de la consulta más reciente a la más antigua."""

    @abstractmethod
    def obtener_por_cita(self, cita_id: int) -> Optional[Consulta]: ...

    @abstractmethod
    def agregar_nota(self, consulta_id: int, nota: NotaAclaratoria) -> None: ...


class IUsuarioRepository(IRepository[Usuario]):
    @abstractmethod
    def obtener_por_nombre_usuario(
        self, nombre_usuario: str, incluir_inactivos: bool = False
    ) -> Optional[Usuario]: ...


class IRecordatorioRepository(IRepository[Recordatorio]):
    @abstractmethod
    def obtener_por_cita(self, cita_id: int) -> Optional[Recordatorio]: ...

    @abstractmethod
    def obtener_pendientes(self, hasta: datetime) -> list[Recordatorio]: ...


class IAuditoriaRepository(ABC):
    """La bitácora solo se escribe y se consulta: nunca se modifica ni se borra."""

    @abstractmethod
    def registrar(self, registro: RegistroAuditoria) -> None: ...

    @abstractmethod
    def consultar(
        self,
        usuario: Optional[str] = None,
        entidad: Optional[str] = None,
        accion: Optional[str] = None,
        limite: int = 200,
    ) -> list[RegistroAuditoria]:
        """Registros más recientes primero."""
