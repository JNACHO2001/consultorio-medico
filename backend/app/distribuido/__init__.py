"""Facturación electrónica distribuida: nodos proveedor concurrentes detrás de un proxy.

Patrones: Proxy (``proxy.py``), Mediator (``mediador.py``), Observer (``eventos.py``) y
Adapter (el proxy cumple ``IProveedorTecnologico``). Los nodos (``nodo.py``) son servidores TCP
con un pool de hilos. Ver ``docs/uml`` para los diagramas de componentes, secuencia y despliegue.
"""
from app.distribuido.cluster import ClusterLocal, ClusterProveedor, NodoProceso, crear_cluster
from app.distribuido.nodo import NodoProveedor
from app.distribuido.proxy import ProveedorProxy

__all__ = [
    "ClusterLocal", "ClusterProveedor", "NodoProceso", "NodoProveedor", "ProveedorProxy", "crear_cluster",
]
