"""Mediador de nodos (patrón Mediator) con circuit breaker por nodo.

El proxy no conoce a los nodos ni sus direcciones: le pide al mediador «despacha este mensaje». El
mediador es el único que sabe qué nodos existen, cuál está menos cargado y cuál está caído.

Circuit breaker de cada nodo:

    CERRADO ──(N fallos seguidos)──► ABIERTO ──(pasa el enfriamiento)──► SEMIABIERTO
       ▲                                ▲                                     │
       └──────────(la sonda responde)───┴──────────(la sonda falla)───────────┘

ABIERTO no recibe tráfico; SEMIABIERTO deja pasar una sola solicitud de prueba (sonda).
Un nodo saturado (OCUPADO) no cuenta como caído: está vivo, solo sin cupo.
"""
from __future__ import annotations

import socket
import threading
import time
from collections import deque
from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable, Optional

from app.distribuido.eventos import CIRCUITO, BusEventos
from app.distribuido.protocolo import MAX_LINEA, ErrorProtocolo, codificar, decodificar


class ErrorConexion(Exception):
    """No se pudo abrir la conexión o el nodo la cerró."""


class ErrorTiempo(Exception):
    """El nodo no respondió dentro del tiempo permitido."""


class SinNodosDisponibles(Exception):
    """Ningún nodo puede recibir tráfico ahora (todos caídos, excluidos u ocupados con su sonda)."""


class ErrorDespacho(Exception):
    """Un intento falló; ``motivo`` es conexion, timeout, saturado o error_nodo."""

    def __init__(self, nodo: str, motivo: str) -> None:
        super().__init__(f"{nodo}: {motivo}")
        self.nodo = nodo
        self.motivo = motivo


class EstadoCircuito(str, Enum):
    CERRADO = "CERRADO"
    ABIERTO = "ABIERTO"
    SEMIABIERTO = "SEMIABIERTO"


class _Conexion:
    def __init__(self, sock: socket.socket) -> None:
        self.sock = sock
        self.lector = sock.makefile("rb")

    def cerrar(self) -> None:
        for cerrable in (self.lector, self.sock):
            try:
                cerrable.close()
            except OSError:
                pass


class ClienteNodo:
    """Cliente TCP de un nodo, con un pool de conexiones persistentes (evita un handshake por documento)."""

    def __init__(self, host: str, puerto: int, max_inactivas: int = 16, timeout_conexion: float = 1.0) -> None:
        self.host, self.puerto = host, puerto
        self._max_inactivas = max_inactivas
        self._timeout_conexion = timeout_conexion
        self._inactivas: deque[_Conexion] = deque()
        self._lock = threading.Lock()

    def solicitar(self, mensaje: dict[str, Any], timeout: float) -> dict[str, Any]:
        with self._lock:
            conexion = self._inactivas.pop() if self._inactivas else None
        if conexion is not None:
            try:
                return self._intercambiar(conexion, mensaje, timeout)
            except ErrorTiempo:
                raise
            except ErrorConexion:
                pass  # conexión inactiva que el nodo ya había cerrado: se intenta una vez con una nueva
        return self._intercambiar(self._abrir(), mensaje, timeout)

    def _abrir(self) -> _Conexion:
        try:
            sock = socket.create_connection((self.host, self.puerto), timeout=self._timeout_conexion)
        except OSError as error:
            raise ErrorConexion(f"No se pudo conectar a {self.host}:{self.puerto}") from error
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        return _Conexion(sock)

    def _intercambiar(self, conexion: _Conexion, mensaje: dict[str, Any], timeout: float) -> dict[str, Any]:
        try:
            conexion.sock.settimeout(timeout)
            conexion.sock.sendall(codificar(mensaje))
            linea = conexion.lector.readline(MAX_LINEA + 1)
            if not linea:
                raise ErrorConexion("El nodo cerró la conexión.")
            respuesta = decodificar(linea)
            if respuesta.get("id") != mensaje.get("id"):
                raise ErrorConexion("Respuesta de otra solicitud.")
        except socket.timeout as error:
            conexion.cerrar()
            raise ErrorTiempo(f"Sin respuesta de {self.host}:{self.puerto} en {timeout}s") from error
        except (OSError, ErrorProtocolo, ErrorConexion) as error:
            conexion.cerrar()
            if isinstance(error, ErrorConexion):
                raise
            raise ErrorConexion(str(error)) from error
        with self._lock:
            if len(self._inactivas) < self._max_inactivas:
                self._inactivas.append(conexion)
                return respuesta
        conexion.cerrar()
        return respuesta

    def cerrar(self) -> None:
        with self._lock:
            conexiones, self._inactivas = list(self._inactivas), deque()
        for conexion in conexiones:
            conexion.cerrar()


@dataclass
class _Destino:
    nombre: str
    cliente: ClienteNodo
    estado: EstadoCircuito = EstadoCircuito.CERRADO
    fallos_seguidos: int = 0
    abierto_hasta: float = 0.0
    sonda_en_curso: bool = False
    en_curso: int = 0
    enviados: int = 0
    exitos: int = 0
    fallos: int = 0
    saturaciones: int = 0
    ultimo_estado: Optional[dict[str, Any]] = None


class MediadorNodos:
    def __init__(
        self,
        destinos: Iterable[tuple[str, int]],
        bus: BusEventos,
        umbral_fallos: int = 3,
        enfriamiento_seg: float = 2.0,
        max_conexiones: int = 16,
    ) -> None:
        self._destinos = [
            _Destino(f"{host}:{puerto}", ClienteNodo(host, puerto, max_inactivas=max_conexiones))
            for host, puerto in destinos
        ]
        self._bus = bus
        self._umbral = umbral_fallos
        self._enfriamiento = enfriamiento_seg
        self._lock = threading.Lock()
        self._turno = 0

    @property
    def cantidad(self) -> int:
        return len(self._destinos)

    # ------------------------------------------------------------------ despacho

    def despachar(self, mensaje: dict[str, Any], timeout: float, excluir: Iterable[str] = ()) -> tuple[str, dict[str, Any]]:
        """Un intento: elige un nodo, le envía el mensaje y registra el resultado."""
        destino = self._reservar(set(excluir))
        if destino is None:
            raise SinNodosDisponibles("Ningún nodo disponible.")
        try:
            try:
                respuesta = destino.cliente.solicitar(mensaje, timeout)
            except ErrorTiempo as error:
                self._fallo(destino)
                raise ErrorDespacho(destino.nombre, "timeout") from error
            except ErrorConexion as error:
                self._fallo(destino)
                raise ErrorDespacho(destino.nombre, "conexion") from error
        finally:
            with self._lock:
                destino.en_curso -= 1
        if not respuesta.get("ok"):
            if respuesta.get("error") == "OCUPADO":
                self._saturado(destino)
                raise ErrorDespacho(destino.nombre, "saturado")
            self._fallo(destino)
            raise ErrorDespacho(destino.nombre, "error_nodo")
        self._exito(destino)
        return destino.nombre, respuesta

    def _reservar(self, excluir: set[str]) -> Optional[_Destino]:
        """Menos solicitudes en curso primero; el empate se reparte por turnos. Respeta los circuitos."""
        with self._lock:
            ahora = time.monotonic()
            candidatos = []
            for destino in self._destinos:
                if destino.nombre in excluir:
                    continue
                if destino.estado == EstadoCircuito.ABIERTO:
                    if ahora < destino.abierto_hasta:
                        continue
                    self._cambiar(destino, EstadoCircuito.SEMIABIERTO)
                if destino.estado == EstadoCircuito.SEMIABIERTO and destino.sonda_en_curso:
                    continue
                candidatos.append(destino)
            if not candidatos:
                return None
            self._turno += 1
            n = len(self._destinos)
            elegido = min(candidatos, key=lambda d: (d.en_curso, (self._destinos.index(d) - self._turno) % n))
            if elegido.estado == EstadoCircuito.SEMIABIERTO:
                elegido.sonda_en_curso = True
            elegido.en_curso += 1
            elegido.enviados += 1
            return elegido

    # ------------------------------------------------------------------ circuit breaker

    def _cambiar(self, destino: _Destino, estado: EstadoCircuito) -> None:
        if destino.estado != estado:
            destino.estado = estado
            self._bus.publicar(CIRCUITO, nodo=destino.nombre, estado=estado.value)

    def _exito(self, destino: _Destino) -> None:
        with self._lock:
            destino.exitos += 1
            destino.fallos_seguidos = 0
            destino.sonda_en_curso = False
            self._cambiar(destino, EstadoCircuito.CERRADO)

    def _saturado(self, destino: _Destino) -> None:
        with self._lock:  # está vivo: responde, solo que sin cupo
            destino.saturaciones += 1
            destino.fallos_seguidos = 0
            destino.sonda_en_curso = False
            self._cambiar(destino, EstadoCircuito.CERRADO)

    def _fallo(self, destino: _Destino) -> None:
        with self._lock:
            destino.fallos += 1
            destino.fallos_seguidos += 1
            destino.sonda_en_curso = False
            if destino.estado == EstadoCircuito.SEMIABIERTO or destino.fallos_seguidos >= self._umbral:
                destino.abierto_hasta = time.monotonic() + self._enfriamiento
                self._cambiar(destino, EstadoCircuito.ABIERTO)

    # ------------------------------------------------------------------ vigilancia

    def sondear(self, timeout: float = 1.0) -> None:
        """Latido: pide el estado a cada nodo para actualizar el circuito y mostrar su carga."""
        for destino in self._destinos:
            with self._lock:
                if destino.sonda_en_curso:
                    continue
                if destino.estado == EstadoCircuito.ABIERTO:
                    if time.monotonic() < destino.abierto_hasta:
                        continue
                    self._cambiar(destino, EstadoCircuito.SEMIABIERTO)
                if destino.estado == EstadoCircuito.SEMIABIERTO:
                    destino.sonda_en_curso = True
            try:
                respuesta = destino.cliente.solicitar({"id": 0, "tipo": "ESTADO"}, timeout)
            except (ErrorConexion, ErrorTiempo):
                self._fallo(destino)
                continue
            if respuesta.get("ok"):
                destino.ultimo_estado = respuesta.get("estado")
                self._exito(destino)
            else:
                self._fallo(destino)

    def estado(self) -> list[dict[str, Any]]:
        with self._lock:
            return [
                {
                    "nodo": d.nombre, "circuito": d.estado.value, "en_curso": d.en_curso, "enviados": d.enviados,
                    "exitos": d.exitos, "fallos": d.fallos, "saturaciones": d.saturaciones,
                    "fallos_seguidos": d.fallos_seguidos, "carga": d.ultimo_estado,
                }
                for d in self._destinos
            ]

    def cerrar(self) -> None:
        for destino in self._destinos:
            destino.cliente.cerrar()
