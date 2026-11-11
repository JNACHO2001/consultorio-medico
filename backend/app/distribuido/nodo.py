"""Nodo proveedor: un servidor TCP con un pool de hilos que procesa documentos electrónicos.

Cada nodo es independiente: puede correr en su propio proceso (``python -m app.distribuido.nodo``)
o, en las pruebas, en un hilo del mismo proceso. Cómo maneja la concurrencia:

* Un hilo por conexión entrante lee solicitudes (``socketserver.ThreadingTCPServer``).
* El trabajo pesado lo hace un pool fijo de ``hilos`` trabajadores.
* Admisión acotada: caben ``hilos + cola`` solicitudes a la vez. Si llega otra, el nodo responde
  ``OCUPADO`` de inmediato (contrapresión) en vez de encolar sin límite; el proxy la manda a otro nodo.
* Idempotencia: una clave ya procesada se responde desde un caché, y una clave que está en proceso
  comparte el resultado (no se hace el trabajo dos veces).
* ``latencia_ms``, ``prob_error`` y ``detener()`` permiten simular la red, el proveedor lento y fallos.
"""
from __future__ import annotations

import argparse
import logging
import random
import signal
import socket
import socketserver
import threading
import time
from collections import OrderedDict
from concurrent.futures import Future, ThreadPoolExecutor
from concurrent.futures import TimeoutError as TiempoAgotado
from typing import Any, Optional

from app.config import cargar_configuracion
from app.distribuido.protocolo import (
    MAX_LINEA,
    ErrorProtocolo,
    decodificar,
    dict_a_documento,
    enviar_mensaje,
)
from app.services.dian import IProveedorTecnologico, ProveedorSimulado

registro = logging.getLogger("consultorio.distribuido.nodo")

CACHE_MAXIMO = 20_000


class _Servidor(socketserver.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = True
    request_queue_size = 256


class _Manejador(socketserver.BaseRequestHandler):
    """Atiende una conexión: lee líneas JSON y responde cada una, hasta que el cliente cierre."""

    def handle(self) -> None:
        nodo: NodoProveedor = self.server.nodo  # type: ignore[attr-defined]
        conexion: socket.socket = self.request
        conexion.settimeout(nodo.inactividad_seg)
        nodo._registrar_conexion(conexion)
        lector = conexion.makefile("rb")
        try:
            while True:
                try:
                    linea = lector.readline(MAX_LINEA + 1)
                except (OSError, ValueError):
                    return
                if not linea or len(linea) > MAX_LINEA:
                    return
                try:
                    respuesta = nodo.atender(decodificar(linea))
                except ErrorProtocolo:
                    respuesta = {"id": None, "ok": False, "error": "SOLICITUD_INVALIDA", "nodo": nodo.nombre}
                try:
                    enviar_mensaje(conexion, respuesta)
                except OSError:
                    return
        finally:
            nodo._olvidar_conexion(conexion)
            try:
                lector.close()
            except OSError:
                pass


class NodoProveedor:
    def __init__(
        self,
        nombre: str = "nodo",
        host: str = "127.0.0.1",
        puerto: int = 0,
        hilos: int = 4,
        cola: int = 16,
        latencia_ms: float = 40.0,
        jitter: float = 0.25,
        prob_error: float = 0.0,
        proveedor: Optional[IProveedorTecnologico] = None,
        inactividad_seg: float = 60.0,
        espera_max_seg: float = 30.0,
        semilla: Optional[int] = None,
    ) -> None:
        self.nombre = nombre
        self.host = host
        self.puerto = puerto
        self.hilos = hilos
        self.cola = cola
        self.latencia_ms = latencia_ms
        self.jitter = jitter
        self.prob_error = prob_error
        self.inactividad_seg = inactividad_seg
        self.espera_max_seg = espera_max_seg
        self._proveedor = proveedor or ProveedorSimulado(cargar_configuracion())
        self._azar = random.Random(semilla)
        self._lock = threading.Lock()
        self._cupos = threading.BoundedSemaphore(hilos + cola)
        self._cache: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self._en_vuelo: dict[str, Future] = {}
        self._conexiones: set[socket.socket] = set()
        self._pool: Optional[ThreadPoolExecutor] = None
        self._servidor: Optional[_Servidor] = None
        self._hilo_servidor: Optional[threading.Thread] = None
        self._inicio = 0.0
        self._activos = 0
        self._contadores = {"aceptadas": 0, "procesadas": 0, "saturadas": 0, "duplicadas": 0, "errores": 0}

    # ------------------------------------------------------------------ ciclo de vida

    def iniciar(self) -> int:
        """Abre el puerto (0 = uno libre) y empieza a atender. Devuelve el puerto real."""
        self._pool = ThreadPoolExecutor(max_workers=self.hilos, thread_name_prefix=f"{self.nombre}-hilo")
        self._servidor = _Servidor((self.host, self.puerto), _Manejador)
        self._servidor.nodo = self  # type: ignore[attr-defined]
        self.puerto = self._servidor.server_address[1]
        self._inicio = time.monotonic()
        self._hilo_servidor = threading.Thread(
            target=self._servidor.serve_forever, kwargs={"poll_interval": 0.05},
            name=f"{self.nombre}-servidor", daemon=True,
        )
        self._hilo_servidor.start()
        registro.info("%s escuchando en %s:%s con %s hilos y cola de %s", self.nombre, self.host, self.puerto,
                      self.hilos, self.cola)
        return self.puerto

    def detener(self) -> None:
        """Cierra el puerto y corta las conexiones abiertas, como si el nodo se cayera."""
        if self._servidor is None:
            return
        self._servidor.shutdown()
        self._servidor.server_close()
        with self._lock:
            abiertas = list(self._conexiones)
        for conexion in abiertas:
            try:
                conexion.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            conexion.close()
        if self._pool is not None:
            self._pool.shutdown(wait=False, cancel_futures=True)
        self._servidor = None

    def _registrar_conexion(self, conexion: socket.socket) -> None:
        with self._lock:
            self._conexiones.add(conexion)

    def _olvidar_conexion(self, conexion: socket.socket) -> None:
        with self._lock:
            self._conexiones.discard(conexion)

    # ------------------------------------------------------------------ atención de solicitudes

    def estado(self) -> dict[str, Any]:
        with self._lock:
            return {
                "nombre": self.nombre,
                "hilos": self.hilos,
                "capacidad_cola": self.cola,
                "en_proceso": self._activos,
                "en_espera": max(0, len(self._en_vuelo) - self._activos),
                "cache": len(self._cache),
                "conexiones": len(self._conexiones),
                "uptime_seg": round(time.monotonic() - self._inicio, 1) if self._inicio else 0.0,
                **self._contadores,
            }

    def atender(self, mensaje: dict[str, Any]) -> dict[str, Any]:
        base = {"id": mensaje.get("id"), "nodo": self.nombre}
        tipo = mensaje.get("tipo")
        if tipo == "PING":
            return {**base, "ok": True}
        if tipo == "ESTADO":
            return {**base, "ok": True, "estado": self.estado()}
        if tipo == "ENVIAR":
            return {**base, **self._enviar(mensaje)}
        return {**base, "ok": False, "error": "SOLICITUD_INVALIDA"}

    def _enviar(self, mensaje: dict[str, Any]) -> dict[str, Any]:
        clave, documento = mensaje.get("clave"), mensaje.get("documento")
        if not clave or not isinstance(documento, dict):
            return {"ok": False, "error": "SOLICITUD_INVALIDA"}
        espera_existente: Optional[Future] = None
        with self._lock:
            if clave in self._cache:  # ya procesada: idempotencia
                self._contadores["duplicadas"] += 1
                self._cache.move_to_end(clave)
                return dict(self._cache[clave])
            if clave in self._en_vuelo:  # en proceso: se comparte el resultado
                self._contadores["duplicadas"] += 1
                espera_existente = self._en_vuelo[clave]
            elif not self._cupos.acquire(blocking=False):  # sin cupo: contrapresión
                self._contadores["saturadas"] += 1
                return {"ok": False, "error": "OCUPADO"}
            else:
                futuro: Future = Future()
                self._en_vuelo[clave] = futuro
                self._contadores["aceptadas"] += 1
        if espera_existente is None:
            try:
                self._pool.submit(self._trabajo, clave, documento, futuro)  # type: ignore[union-attr]
            except RuntimeError:  # el nodo se está apagando
                self._cupos.release()
                with self._lock:
                    self._en_vuelo.pop(clave, None)
                return {"ok": False, "error": "ERROR_NODO"}
            espera_existente = futuro
        try:
            return dict(espera_existente.result(timeout=self.espera_max_seg))
        except (TiempoAgotado, Exception):  # noqa: BLE001
            return {"ok": False, "error": "ERROR_NODO"}

    def _trabajo(self, clave: str, documento: dict[str, Any], futuro: Future) -> None:
        inicio = time.perf_counter()
        with self._lock:
            self._activos += 1
        try:
            self._simular_proceso()
            respuesta = self._proveedor.enviar(dict_a_documento(documento))
            resultado = {
                "ok": True, "aceptado": respuesta.aceptado, "codigo": respuesta.codigo,
                "mensaje": respuesta.mensaje, "ms": round((time.perf_counter() - inicio) * 1000, 2),
            }
            with self._lock:
                self._activos -= 1
                self._contadores["procesadas"] += 1
                self._cache[clave] = resultado
                while len(self._cache) > CACHE_MAXIMO:
                    self._cache.popitem(last=False)
                self._en_vuelo.pop(clave, None)
        except Exception:  # noqa: BLE001 - el error se informa al proxy, que reintenta en otro nodo
            registro.exception("%s: error al procesar %s", self.nombre, clave)
            resultado = {"ok": False, "error": "ERROR_NODO"}
            with self._lock:
                self._activos -= 1
                self._contadores["errores"] += 1
                self._en_vuelo.pop(clave, None)
        finally:
            self._cupos.release()
        futuro.set_result(resultado)

    def _simular_proceso(self) -> None:
        """Representa la firma y la transmisión al proveedor: espera de red y fallos ocasionales."""
        if self.latencia_ms > 0:
            factor = 1 + self.jitter * (2 * self._azar.random() - 1)
            time.sleep(self.latencia_ms * factor / 1000)
        if self.prob_error and self._azar.random() < self.prob_error:
            raise RuntimeError("fallo inyectado")


def principal(argumentos: Optional[list[str]] = None) -> None:
    analizador = argparse.ArgumentParser(description="Nodo proveedor de facturación electrónica (simulado).")
    analizador.add_argument("--nombre", default="nodo")
    analizador.add_argument("--host", default="127.0.0.1")
    analizador.add_argument("--puerto", type=int, default=0, help="0 = elegir un puerto libre")
    analizador.add_argument("--hilos", type=int, default=4)
    analizador.add_argument("--cola", type=int, default=16)
    analizador.add_argument("--latencia-ms", type=float, default=40.0)
    analizador.add_argument("--jitter", type=float, default=0.25)
    analizador.add_argument("--prob-error", type=float, default=0.0)
    a = analizador.parse_args(argumentos)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    nodo = NodoProveedor(a.nombre, a.host, a.puerto, a.hilos, a.cola, a.latencia_ms, a.jitter, a.prob_error)
    puerto = nodo.iniciar()
    print(f"LISTO {puerto}", flush=True)  # el lanzador lee esta línea para conocer el puerto

    salir = threading.Event()
    for senal in (signal.SIGINT, signal.SIGTERM):
        signal.signal(senal, lambda *_: salir.set())
    salir.wait()
    nodo.detener()


if __name__ == "__main__":
    principal()
