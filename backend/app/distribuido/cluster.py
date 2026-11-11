"""Composición del clúster del lado de la API y lanzador local de nodos (para demostrar y medir).

* ``ClusterProveedor``: bus de eventos + métricas + mediador + proxy + hilo vigilante (latidos).
* ``ClusterLocal``: arranca N nodos como **procesos del sistema operativo** en esta máquina.

Demostración con tres nodos::

    cd backend
    python -m app.distribuido.cluster --nodos 3          # imprime la variable NODOS_PROVEEDOR
    NODOS_PROVEEDOR=127.0.0.1:9101,127.0.0.1:9102,127.0.0.1:9103 uvicorn app.main:crear_app --factory
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any, Optional

from app.config import Configuracion
from app.distribuido.eventos import BusEventos, Metricas
from app.distribuido.mediador import MediadorNodos
from app.distribuido.proxy import ProveedorProxy

BACKEND = Path(__file__).resolve().parents[2]


def analizar_destino(texto: str) -> tuple[str, int]:
    host, _, puerto = texto.strip().rpartition(":")
    if not host or not puerto.isdigit():
        raise ValueError(f"Nodo con formato inválido (use host:puerto): {texto!r}")
    return host, int(puerto)


class ClusterProveedor:
    def __init__(
        self,
        destinos: list[tuple[str, int]],
        timeout_seg: float = 3.0,
        max_intentos: int = 4,
        umbral_fallos: int = 3,
        enfriamiento_seg: float = 2.0,
        intervalo_latido_seg: float = 2.0,
        max_conexiones: int = 16,
    ) -> None:
        self.bus = BusEventos()
        self.metricas = Metricas(self.bus)
        self.mediador = MediadorNodos(destinos, self.bus, umbral_fallos, enfriamiento_seg, max_conexiones)
        self.proxy = ProveedorProxy(self.mediador, self.bus, max_intentos, timeout_seg)
        self._intervalo = intervalo_latido_seg
        self._parar = threading.Event()
        self._vigilante: Optional[threading.Thread] = None

    def iniciar(self) -> None:
        self.bus.iniciar()
        self._parar.clear()
        self._vigilante = threading.Thread(target=self._latidos, name="vigilante-nodos", daemon=True)
        self._vigilante.start()

    def detener(self) -> None:
        self._parar.set()
        if self._vigilante is not None:
            self._vigilante.join(timeout=3)
        self.bus.detener()
        self.mediador.cerrar()

    def _latidos(self) -> None:
        while not self._parar.wait(self._intervalo):
            self.mediador.sondear()

    def estado(self) -> dict[str, Any]:
        return {
            "nodos": self.mediador.estado(),
            "metricas": self.metricas.resumen(),
            "eventos_descartados": self.bus.descartados,
        }


def crear_cluster(config: Configuracion) -> Optional[ClusterProveedor]:
    """Devuelve el clúster si hay nodos configurados (NODOS_PROVEEDOR); si no, None y se usa el proveedor local."""
    if not config.nodos_proveedor:
        return None
    return ClusterProveedor(
        [analizar_destino(n) for n in config.nodos_proveedor],
        timeout_seg=config.proxy_timeout_seg,
        max_intentos=config.proxy_max_intentos,
        umbral_fallos=config.circuito_fallos,
        enfriamiento_seg=config.circuito_enfriamiento_seg,
    )


# ---------------------------------------------------------------------- nodos como procesos


class NodoProceso:
    """Un nodo proveedor corriendo en su propio proceso del sistema operativo."""

    def __init__(self, nombre: str, puerto: int = 0, hilos: int = 4, cola: int = 16, latencia_ms: float = 40.0,
                 jitter: float = 0.25, prob_error: float = 0.0) -> None:
        self.nombre, self.puerto = nombre, puerto
        self._argumentos = ["--hilos", str(hilos), "--cola", str(cola), "--latencia-ms", str(latencia_ms),
                            "--jitter", str(jitter), "--prob-error", str(prob_error)]
        self._proceso: Optional[subprocess.Popen] = None

    def iniciar(self, espera_seg: float = 30.0) -> int:
        self._proceso = subprocess.Popen(
            [sys.executable, "-m", "app.distribuido.nodo", "--nombre", self.nombre, "--puerto", str(self.puerto),
             *self._argumentos],
            cwd=BACKEND, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
        )
        guardia = threading.Timer(espera_seg, self._proceso.kill)
        guardia.start()
        try:
            linea = self._proceso.stdout.readline()  # type: ignore[union-attr]
        finally:
            guardia.cancel()
        if not linea.startswith("LISTO"):
            self.matar()
            raise RuntimeError(f"El nodo {self.nombre} no arrancó.")
        self.puerto = int(linea.split()[1])
        return self.puerto

    @property
    def vivo(self) -> bool:
        return self._proceso is not None and self._proceso.poll() is None

    def detener(self) -> None:
        """Apagado ordenado (SIGTERM)."""
        if self.vivo:
            self._proceso.terminate()  # type: ignore[union-attr]
            try:
                self._proceso.wait(timeout=5)  # type: ignore[union-attr]
            except subprocess.TimeoutExpired:
                self.matar()

    def matar(self) -> None:
        """Caída abrupta (SIGKILL): así se prueba la tolerancia a fallos."""
        if self._proceso is not None:
            self._proceso.kill()
            self._proceso.wait()


class ClusterLocal:
    """Administrador de contexto: arranca ``n`` nodos en procesos y los apaga al salir."""

    def __init__(self, n: int, **opciones: Any) -> None:
        self.nodos = [NodoProceso(f"nodo-{i + 1}", **opciones) for i in range(n)]

    def __enter__(self) -> "ClusterLocal":
        try:
            for nodo in self.nodos:
                nodo.iniciar()
        except Exception:
            self.__exit__(None, None, None)
            raise
        return self

    def __exit__(self, *_: Any) -> None:
        for nodo in self.nodos:
            nodo.detener()

    @property
    def destinos(self) -> list[tuple[str, int]]:
        return [("127.0.0.1", n.puerto) for n in self.nodos]

    def reiniciar(self, indice: int) -> None:
        """Levanta de nuevo un nodo caído en el mismo puerto."""
        nodo = self.nodos[indice]
        nodo.detener()
        nodo.iniciar()


def principal() -> None:
    analizador = argparse.ArgumentParser(description="Arranca N nodos proveedor en procesos locales.")
    analizador.add_argument("--nodos", type=int, default=3)
    analizador.add_argument("--hilos", type=int, default=4)
    analizador.add_argument("--cola", type=int, default=16)
    analizador.add_argument("--latencia-ms", type=float, default=40.0)
    a = analizador.parse_args()
    with ClusterLocal(a.nodos, hilos=a.hilos, cola=a.cola, latencia_ms=a.latencia_ms) as cluster:
        lista = ",".join(f"{h}:{p}" for h, p in cluster.destinos)
        print(f"NODOS_PROVEEDOR={lista}", flush=True)
        print("Nodos en marcha. Ctrl+C para detenerlos.", flush=True)
        try:
            threading.Event().wait()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    principal()
