"""Bus de eventos y métricas (patrón Observer).

El proxy y el mediador no saben quién escucha: solo publican hechos («envío exitoso»,
«intento fallido», «el circuito de un nodo cambió»). Los observadores (métricas, bitácora)
se suscriben y los reciben en un hilo propio, así que observar no frena el camino de la
factura electrónica. Si la cola se llena, el evento se descarta y se cuenta: la
observabilidad nunca debe tumbar la operación.
"""
from __future__ import annotations

import logging
import queue
import threading
import time
from collections import Counter, defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

registro = logging.getLogger("consultorio.distribuido")

# Tipos de evento que se publican.
ENVIO_EXITOSO = "envio.exitoso"      # nodo, ms, intentos, aceptado
ENVIO_FALLIDO = "envio.fallido"      # intentos, motivo
INTENTO_FALLIDO = "intento.fallido"  # nodo, motivo (conexion | timeout | saturado | error_nodo | sin_nodos)
CIRCUITO = "nodo.circuito"           # nodo, estado (CERRADO | ABIERTO | SEMIABIERTO)


@dataclass(frozen=True)
class Evento:
    tipo: str
    datos: dict[str, Any]
    momento: float = field(default_factory=time.time)


class BusEventos:
    def __init__(self, capacidad: int = 20_000) -> None:
        self._cola: queue.Queue[Optional[Evento]] = queue.Queue(maxsize=capacidad)
        self._suscriptores: dict[str, list[Callable[[Evento], None]]] = defaultdict(list)
        self._hilo: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self.descartados = 0

    def suscribir(self, tipo: str, observador: Callable[[Evento], None]) -> None:
        """``tipo`` es un tipo concreto o ``"*"`` para recibirlos todos."""
        with self._lock:
            self._suscriptores[tipo].append(observador)

    def publicar(self, tipo: str, **datos: Any) -> None:
        try:
            self._cola.put_nowait(Evento(tipo, datos))
        except queue.Full:
            self.descartados += 1

    # ------------------------------------------------------------------ hilo despachador

    def iniciar(self) -> None:
        if self._hilo is not None and self._hilo.is_alive():
            return
        self._hilo = threading.Thread(target=self._despachar, name="bus-eventos", daemon=True)
        self._hilo.start()

    def detener(self) -> None:
        if self._hilo is None:
            return
        self._cola.put(None)
        self._hilo.join(timeout=2)
        self._hilo = None

    def vaciar(self) -> None:
        """Espera a que se entreguen los eventos pendientes (útil en pruebas y al medir)."""
        self._cola.join()

    def _despachar(self) -> None:
        while True:
            evento = self._cola.get()
            try:
                if evento is None:
                    return
                with self._lock:
                    observadores = [*self._suscriptores.get(evento.tipo, ()), *self._suscriptores.get("*", ())]
                for observador in observadores:
                    try:
                        observador(evento)
                    except Exception:  # noqa: BLE001 - un observador defectuoso no afecta a los demás
                        registro.exception("Falló un observador del evento %s", evento.tipo)
            finally:
                self._cola.task_done()


def _percentil(ordenados: list[float], p: float) -> float:
    if not ordenados:
        return 0.0
    posicion = (len(ordenados) - 1) * p
    inferior = int(posicion)
    superior = min(inferior + 1, len(ordenados) - 1)
    return ordenados[inferior] + (ordenados[superior] - ordenados[inferior]) * (posicion - inferior)


class Metricas:
    """Observador que resume lo que ocurre: totales, reintentos, reparto por nodo y latencias."""

    def __init__(self, bus: BusEventos) -> None:
        self._lock = threading.Lock()
        self._latencias: deque[float] = deque(maxlen=100_000)
        self._por_nodo: Counter[str] = Counter()
        self._fallos_por_motivo: Counter[str] = Counter()
        self._circuitos: list[dict[str, Any]] = []
        self._totales: Counter[str] = Counter()
        bus.suscribir(ENVIO_EXITOSO, self._exitoso)
        bus.suscribir(ENVIO_FALLIDO, self._fallido)
        bus.suscribir(INTENTO_FALLIDO, self._intento)
        bus.suscribir(CIRCUITO, self._circuito)

    def _exitoso(self, e: Evento) -> None:
        with self._lock:
            self._totales["documentos"] += 1
            self._totales["aceptados" if e.datos.get("aceptado") else "rechazados_por_proveedor"] += 1
            self._totales["reintentos"] += max(0, e.datos.get("intentos", 1) - 1)
            self._por_nodo[e.datos["nodo"]] += 1
            self._latencias.append(e.datos["ms"])

    def _fallido(self, e: Evento) -> None:
        with self._lock:
            self._totales["documentos"] += 1
            self._totales["sin_respuesta"] += 1

    def _intento(self, e: Evento) -> None:
        with self._lock:
            self._fallos_por_motivo[e.datos.get("motivo", "desconocido")] += 1

    def _circuito(self, e: Evento) -> None:
        with self._lock:
            self._circuitos.append({"nodo": e.datos["nodo"], "estado": e.datos["estado"], "momento": e.momento})
            del self._circuitos[:-50]

    def resumen(self, circuitos: int = 10) -> dict[str, Any]:
        with self._lock:
            ordenadas = sorted(self._latencias)
            return {
                **{k: self._totales.get(k, 0) for k in (
                    "documentos", "aceptados", "rechazados_por_proveedor", "sin_respuesta", "reintentos")},
                "por_nodo": dict(self._por_nodo),
                "intentos_fallidos": dict(self._fallos_por_motivo),
                "cambios_de_circuito": list(self._circuitos[-circuitos:]),
                "latencia_ms": {
                    "media": round(sum(ordenadas) / len(ordenadas), 2) if ordenadas else 0.0,
                    "p50": round(_percentil(ordenadas, 0.50), 2),
                    "p95": round(_percentil(ordenadas, 0.95), 2),
                    "p99": round(_percentil(ordenadas, 0.99), 2),
                    "max": round(ordenadas[-1], 2) if ordenadas else 0.0,
                },
            }

    def reiniciar(self) -> None:
        with self._lock:
            self._latencias.clear()
            self._por_nodo.clear()
            self._fallos_por_motivo.clear()
            self._circuitos.clear()
            self._totales.clear()
