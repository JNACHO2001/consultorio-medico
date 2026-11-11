"""Proxy remoto del proveedor tecnológico (patrón Proxy).

``ProveedorProxy`` cumple la misma interfaz que el proveedor simulado (``IProveedorTecnologico``),
así que ``FacturacionElectronicaService`` no sabe si habla con un objeto local o con un clúster de
nodos. Lo que añade el proxy:

* serializa el documento y lo manda al nodo que elija el mediador;
* reintenta con espera exponencial y jitter, probando otro nodo en cada intento;
* usa una clave de idempotencia, de modo que reintentar nunca duplica el trabajo;
* si ningún nodo responde, degrada con elegancia: devuelve un rechazo ``NODOS-01`` y el documento
  queda RECHAZADO, listo para el «Reintentar» que ya existe en el sistema (no se pierde la factura).
"""
from __future__ import annotations

import itertools
import random
import time

from app.distribuido.eventos import ENVIO_EXITOSO, ENVIO_FALLIDO, INTENTO_FALLIDO, BusEventos
from app.distribuido.mediador import ErrorDespacho, MediadorNodos, SinNodosDisponibles
from app.distribuido.protocolo import clave_idempotencia, documento_a_dict
from app.domain.modelos import DocumentoElectronico
from app.services.dian import IProveedorTecnologico, RespuestaProveedor

CODIGO_SIN_NODOS = "NODOS-01"


class ProveedorProxy(IProveedorTecnologico):
    def __init__(
        self,
        mediador: MediadorNodos,
        bus: BusEventos,
        max_intentos: int = 4,
        timeout_seg: float = 3.0,
        espera_base_seg: float = 0.05,
        espera_max_seg: float = 1.0,
    ) -> None:
        self._mediador = mediador
        self._bus = bus
        self._max_intentos = max_intentos
        self._timeout = timeout_seg
        self._espera_base = espera_base_seg
        self._espera_max = espera_max_seg
        self._ids = itertools.count(1)  # next() es atómico en CPython

    @property
    def nombre(self) -> str:  # type: ignore[override]
        return f"Proxy hacia {self._mediador.cantidad} nodo(s) proveedor (simulado, sin conexión con la DIAN)"

    def enviar(self, documento: DocumentoElectronico) -> RespuestaProveedor:
        inicio = time.perf_counter()
        mensaje = {
            "id": next(self._ids),
            "tipo": "ENVIAR",
            "clave": clave_idempotencia(documento),
            "documento": documento_a_dict(documento),
        }
        probados: set[str] = set()
        ultimo_motivo = "sin_nodos"
        for intento in range(1, self._max_intentos + 1):
            try:
                nodo, respuesta = self._mediador.despachar(mensaje, self._timeout, probados)
            except SinNodosDisponibles:
                ultimo_motivo = "sin_nodos"
                probados.clear()  # tras la espera se vuelve a considerar a todos
                self._bus.publicar(INTENTO_FALLIDO, nodo=None, motivo=ultimo_motivo, intento=intento)
            except ErrorDespacho as error:
                ultimo_motivo = error.motivo
                probados.add(error.nodo)  # el siguiente intento prueba otro nodo
                self._bus.publicar(INTENTO_FALLIDO, nodo=error.nodo, motivo=error.motivo, intento=intento)
            else:
                self._bus.publicar(
                    ENVIO_EXITOSO, nodo=nodo, ms=(time.perf_counter() - inicio) * 1000, intentos=intento,
                    aceptado=bool(respuesta["aceptado"]),
                )
                return RespuestaProveedor(
                    bool(respuesta["aceptado"]), respuesta["codigo"], f"{respuesta['mensaje']} [{nodo}]"
                )
            if intento < self._max_intentos:
                time.sleep(self._espera(intento))
        self._bus.publicar(ENVIO_FALLIDO, intentos=self._max_intentos, motivo=ultimo_motivo)
        return RespuestaProveedor(
            False, CODIGO_SIN_NODOS,
            f"[{CODIGO_SIN_NODOS}] No se pudo transmitir el documento tras {self._max_intentos} intentos "
            f"({ultimo_motivo}). Use «Reintentar» cuando el proveedor se recupere.",
        )

    def _espera(self, intento: int) -> float:
        """Espera exponencial con jitter: evita que todos los reintentos lleguen a la vez."""
        return min(self._espera_max, self._espera_base * 2 ** (intento - 1)) * (0.5 + random.random())
