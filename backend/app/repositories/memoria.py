"""Implementaciones en memoria de los repositorios.

Cada repositorio guarda sus objetos en una lista de Python, protegida con un
candado porque FastAPI atiende peticiones en varios hilos. Para imitar el
comportamiento de una base de datos, los objetos se guardan y se devuelven
como copias: un servicio solo cambia un dato cuando llama a `actualizar`.

Los repositorios de pacientes y de consultas anotan cada acceso en la bitácora
de auditoría (RF-13); por eso ninguna pantalla ni servicio puede saltársela.
"""
from __future__ import annotations

import copy
import threading
import unicodedata
from datetime import date, datetime, time, timedelta, timezone
from typing import Generic, Optional, TypeVar

from app.core.contexto import obtener_usuario
from app.domain.excepciones import NoEncontrado
from app.domain.modelos import (
    Cita,
    Consulta,
    Entidad,
    EstadoCita,
    EstadoRecordatorio,
    NotaAclaratoria,
    Paciente,
    Recordatorio,
    RegistroAuditoria,
    Usuario,
)
from app.repositories.interfaces import (
    IAuditoriaRepository,
    ICitaRepository,
    IConsultaRepository,
    IPacienteRepository,
    IRecordatorioRepository,
    IRepository,
    IUsuarioRepository,
)

T = TypeVar("T", bound=Entidad)


def _normalizar(texto: str) -> str:
    """Minúsculas y sin tildes, para buscar sin distinguir acentos."""
    descompuesto = unicodedata.normalize("NFKD", texto or "")
    return "".join(c for c in descompuesto if not unicodedata.combining(c)).lower().strip()


def _auditar(
    auditoria: IAuditoriaRepository, entidad: str, accion: str, id_entidad: int = 0
) -> None:
    usuario = obtener_usuario()
    if usuario is None:  # carga de datos demo o tarea interna: no hay quién audite
        return
    auditoria.registrar(
        RegistroAuditoria(
            fecha_hora=datetime.now(timezone.utc),
            usuario_id=usuario.id,
            usuario=usuario.nombre_usuario,
            accion=accion,
            entidad=entidad,
            id_entidad=id_entidad,
        )
    )


class MemoryRepository(IRepository[T], Generic[T]):
    """Repositorio genérico respaldado por una lista de objetos."""

    def __init__(self) -> None:
        self._items: list[T] = []
        self._siguiente_id = 1
        self._lock = threading.RLock()

    def agregar(self, entidad: T) -> T:
        with self._lock:
            guardada = copy.deepcopy(entidad)
            guardada.id = self._siguiente_id
            self._siguiente_id += 1
            self._items.append(guardada)
            return copy.deepcopy(guardada)

    def obtener_por_id(self, id: int) -> Optional[T]:
        with self._lock:
            for item in self._items:
                if item.id == id and item.activo:
                    return copy.deepcopy(item)
        return None

    def actualizar(self, entidad: T) -> T:
        with self._lock:
            for posicion, item in enumerate(self._items):
                if item.id == entidad.id:
                    self._items[posicion] = copy.deepcopy(entidad)
                    return copy.deepcopy(entidad)
        raise NoEncontrado(f"No existe el registro {entidad.id}.")

    def desactivar(self, id: int) -> None:
        """Borrado lógico: el registro se conserva, solo se marca como inactivo."""
        with self._lock:
            for item in self._items:
                if item.id == id:
                    item.activo = False
                    return
        raise NoEncontrado(f"No existe el registro {id}.")

    def listar(self, incluir_inactivos: bool = False) -> list[T]:
        with self._lock:
            return [
                copy.deepcopy(item)
                for item in self._items
                if incluir_inactivos or item.activo
            ]


class MemoryAuditoriaRepository(IAuditoriaRepository):
    def __init__(self) -> None:
        self._registros: list[RegistroAuditoria] = []
        self._siguiente_id = 1
        self._lock = threading.RLock()

    def registrar(self, registro: RegistroAuditoria) -> None:
        with self._lock:
            guardado = copy.deepcopy(registro)
            guardado.id = self._siguiente_id
            self._siguiente_id += 1
            self._registros.append(guardado)

    def consultar(
        self,
        usuario: Optional[str] = None,
        entidad: Optional[str] = None,
        accion: Optional[str] = None,
        limite: int = 200,
    ) -> list[RegistroAuditoria]:
        with self._lock:
            resultado: list[RegistroAuditoria] = []
            for registro in reversed(self._registros):
                if usuario and _normalizar(usuario) not in _normalizar(registro.usuario):
                    continue
                if entidad and registro.entidad.lower() != entidad.lower():
                    continue
                if accion and registro.accion.lower() != accion.lower():
                    continue
                resultado.append(copy.deepcopy(registro))
                if len(resultado) >= limite:
                    break
            return resultado


class MemoryPacienteRepository(MemoryRepository[Paciente], IPacienteRepository):
    def __init__(self, auditoria: IAuditoriaRepository) -> None:
        super().__init__()
        self._auditoria = auditoria

    def agregar(self, entidad: Paciente) -> Paciente:
        nuevo = super().agregar(entidad)
        _auditar(self._auditoria, "Paciente", "CREACION", nuevo.id)
        return nuevo

    def obtener_por_id(self, id: int) -> Optional[Paciente]:
        paciente = super().obtener_por_id(id)
        if paciente is not None:
            _auditar(self._auditoria, "Paciente", "LECTURA", id)
        return paciente

    def actualizar(self, entidad: Paciente) -> Paciente:
        actualizado = super().actualizar(entidad)
        _auditar(self._auditoria, "Paciente", "MODIFICACION", actualizado.id)
        return actualizado

    def desactivar(self, id: int) -> None:
        super().desactivar(id)
        _auditar(self._auditoria, "Paciente", "DESACTIVACION", id)

    def listar(self, incluir_inactivos: bool = False) -> list[Paciente]:
        _auditar(self._auditoria, "Paciente", "LISTADO")
        return super().listar(incluir_inactivos)

    def obtener_por_documento(self, tipo: str, numero: str) -> Optional[Paciente]:
        with self._lock:
            for item in self._items:
                if (
                    item.activo
                    and item.tipo_documento == tipo
                    and item.numero_documento == numero.strip()
                ):
                    _auditar(self._auditoria, "Paciente", "LECTURA", item.id)
                    return copy.deepcopy(item)
        return None

    def buscar(self, texto: str, limite: int = 50) -> list[Paciente]:
        """Busca por documento o por nombre (texto parcial, sin distinguir tildes)."""
        terminos = _normalizar(texto).split()
        with self._lock:
            encontrados = [
                item
                for item in self._items
                if item.activo
                and all(
                    t
                    in " ".join(
                        [
                            item.numero_documento,
                            _normalizar(item.nombres),
                            _normalizar(item.apellidos),
                        ]
                    )
                    for t in terminos
                )
            ]
            encontrados.sort(key=lambda p: (_normalizar(p.apellidos), _normalizar(p.nombres)))
            resultado = [copy.deepcopy(p) for p in encontrados[:limite]]
        _auditar(self._auditoria, "Paciente", "BUSQUEDA")
        return resultado

    def obtener_por_ids(self, ids: list[int]) -> list[Paciente]:
        buscados = set(ids)
        with self._lock:
            resultado = [
                copy.deepcopy(item) for item in self._items if item.activo and item.id in buscados
            ]
        _auditar(self._auditoria, "Paciente", "LECTURA_MULTIPLE")
        return resultado


class MemoryCitaRepository(MemoryRepository[Cita], ICitaRepository):
    def obtener_por_medico_y_fecha(
        self, medico_id: int, fecha: date, dias: int = 1, incluir_canceladas: bool = False
    ) -> list[Cita]:
        inicio = datetime.combine(fecha, time.min)
        fin = inicio + timedelta(days=dias)
        with self._lock:
            citas = [
                copy.deepcopy(c)
                for c in self._items
                if c.activo
                and c.medico_id == medico_id
                and c.fecha_hora is not None
                and inicio <= c.fecha_hora < fin
                and (incluir_canceladas or c.estado != EstadoCita.CANCELADA)
            ]
        citas.sort(key=lambda c: c.fecha_hora)
        return citas

    def existe_cruce(
        self, medico_id: int, fecha_hora: datetime, excluir_cita_id: Optional[int] = None
    ) -> bool:
        """Una cita cancelada libera el horario (RN-06); las demás lo ocupan (RN-02)."""
        with self._lock:
            return any(
                c.activo
                and c.medico_id == medico_id
                and c.fecha_hora == fecha_hora
                and c.estado != EstadoCita.CANCELADA
                and c.id != excluir_cita_id
                for c in self._items
            )

    def actualizar_estado(
        self, cita_id: int, estado: EstadoCita, motivo_cancelacion: Optional[str] = None
    ) -> None:
        with self._lock:
            for cita in self._items:
                if cita.id == cita_id:
                    cita.estado = estado
                    if estado == EstadoCita.CANCELADA:
                        cita.motivo_cancelacion = motivo_cancelacion
                    return
        raise NoEncontrado(f"No existe la cita {cita_id}.")


class MemoryConsultaRepository(MemoryRepository[Consulta], IConsultaRepository):
    def __init__(self, auditoria: IAuditoriaRepository) -> None:
        super().__init__()
        self._auditoria = auditoria

    def agregar(self, entidad: Consulta) -> Consulta:
        nueva = super().agregar(entidad)
        _auditar(self._auditoria, "Consulta", "CREACION", nueva.id)
        return nueva

    def obtener_por_id(self, id: int) -> Optional[Consulta]:
        consulta = super().obtener_por_id(id)
        if consulta is not None:
            _auditar(self._auditoria, "Consulta", "LECTURA", id)
        return consulta

    def actualizar(self, entidad: Consulta) -> Consulta:
        actualizada = super().actualizar(entidad)
        _auditar(self._auditoria, "Consulta", "MODIFICACION", actualizada.id)
        return actualizada

    def desactivar(self, id: int) -> None:
        super().desactivar(id)
        _auditar(self._auditoria, "Consulta", "DESACTIVACION", id)

    def listar(self, incluir_inactivos: bool = False) -> list[Consulta]:
        _auditar(self._auditoria, "Consulta", "LISTADO")
        return super().listar(incluir_inactivos)

    def obtener_por_paciente(self, paciente_id: int) -> list[Consulta]:
        with self._lock:
            consultas = [
                copy.deepcopy(c)
                for c in self._items
                if c.activo and c.paciente_id == paciente_id
            ]
        consultas.sort(key=lambda c: c.fecha_hora or datetime.min, reverse=True)
        _auditar(self._auditoria, "HistoriaClinica", "LECTURA", paciente_id)
        return consultas

    def obtener_por_cita(self, cita_id: int) -> Optional[Consulta]:
        with self._lock:
            for item in self._items:
                if item.activo and item.cita_id == cita_id:
                    _auditar(self._auditoria, "Consulta", "LECTURA", item.id)
                    return copy.deepcopy(item)
        return None

    def agregar_nota(self, consulta_id: int, nota: NotaAclaratoria) -> None:
        with self._lock:
            for item in self._items:
                if item.id == consulta_id and item.activo:
                    item.notas.append(copy.deepcopy(nota))
                    _auditar(self._auditoria, "Consulta", "NOTA_ACLARATORIA", consulta_id)
                    return
        raise NoEncontrado(f"No existe la consulta {consulta_id}.")


class MemoryUsuarioRepository(MemoryRepository[Usuario], IUsuarioRepository):
    def obtener_por_nombre_usuario(
        self, nombre_usuario: str, incluir_inactivos: bool = False
    ) -> Optional[Usuario]:
        buscado = nombre_usuario.strip().lower()
        with self._lock:
            for item in self._items:
                if item.nombre_usuario.lower() == buscado and (incluir_inactivos or item.activo):
                    return copy.deepcopy(item)
        return None


class MemoryRecordatorioRepository(MemoryRepository[Recordatorio], IRecordatorioRepository):
    def obtener_por_cita(self, cita_id: int) -> Optional[Recordatorio]:
        with self._lock:
            for item in reversed(self._items):
                if (
                    item.cita_id == cita_id
                    and item.activo
                    and item.estado == EstadoRecordatorio.PROGRAMADO
                ):
                    return copy.deepcopy(item)
        return None

    def obtener_pendientes(self, hasta: datetime) -> list[Recordatorio]:
        with self._lock:
            return [
                copy.deepcopy(r)
                for r in self._items
                if r.activo
                and r.estado == EstadoRecordatorio.PROGRAMADO
                and r.fecha_envio is not None
                and r.fecha_envio <= hasta
            ]
