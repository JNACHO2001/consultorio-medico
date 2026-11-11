"""Unidad 2: facturación electrónica distribuida (nodos con hilos, proxy, mediador y observadores).

Los nodos corren en hilos de la propia prueba pero hablan por TCP real (127.0.0.1), así que se
ejercita el mismo camino de red que en el despliegue con procesos.
"""
import dataclasses
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

import pytest

from app.distribuido import ClusterProveedor, NodoProveedor
from app.distribuido.eventos import BusEventos, Metricas
from app.distribuido.mediador import ClienteNodo, EstadoCircuito
from app.distribuido.protocolo import clave_idempotencia, dict_a_documento, documento_a_dict
from app.domain.modelos import DocumentoElectronico, TipoDocumentoElectronico
from tests.conftest import iniciar_sesion
from tests.test_convenios_cartera_rips import (  # noqa: F401  (fixtures compartidas)
    admitir,
    catalogo,
    convenios,
    cuenta_con_convenio,
    factura_eps,
    registrar,
    url,
)


def documento(n: int = 0, valor: int = 85_500) -> DocumentoElectronico:
    """Documento que el proveedor simulado acepta (XML bien formado, CUFE de 96 hex, rango y fecha válidos)."""
    return DocumentoElectronico(
        factura_id=n, tipo=TipoDocumentoElectronico.FACTURA, prefijo="SETP", consecutivo=990_000_000 + n,
        fecha=datetime.now() - timedelta(days=1), adquirente_tipo_documento="31", adquirente_documento="800000001",
        adquirente_dv="1", adquirente_nombre="EPS Demo", adquirente_es_pagador=True, valor_bruto=valor, valor=valor,
        cufe=f"{n:096x}", xml="<Invoice><ID>x</ID></Invoice>",
    )


@pytest.fixture
def nodos():
    """Fábrica de nodos en hilos; se apagan al terminar la prueba."""
    creados: list[NodoProveedor] = []

    def crear(n: int = 1, **opciones) -> list[NodoProveedor]:
        opciones = {"latencia_ms": 5.0, "jitter": 0.0, **opciones}
        nuevos = [NodoProveedor(f"nodo-{len(creados) + i + 1}", **opciones) for i in range(n)]
        for nodo in nuevos:
            nodo.iniciar()
        creados.extend(nuevos)
        return nuevos

    yield crear
    for nodo in creados:
        nodo.detener()


@pytest.fixture
def clusters():
    """Fábrica de clústeres del lado de la API (proxy + mediador + observadores)."""
    creados: list[ClusterProveedor] = []

    def crear(nodos_: list[NodoProveedor], **opciones) -> ClusterProveedor:
        opciones = {"timeout_seg": 2.0, "max_intentos": 4, "umbral_fallos": 2, "enfriamiento_seg": 0.3,
                    "intervalo_latido_seg": 3600, **opciones}
        cluster = ClusterProveedor([(n.host, n.puerto) for n in nodos_], **opciones)
        cluster.iniciar()
        creados.append(cluster)
        return cluster

    yield crear
    for cluster in creados:
        cluster.detener()


# ------------------------------------------------------------------ protocolo


def test_el_documento_viaja_completo_por_el_protocolo():
    original = documento(7)
    copia = dict_a_documento(documento_a_dict(original))
    assert (copia.numero, copia.cufe, copia.valor, copia.tipo, copia.fecha) == (
        original.numero, original.cufe, original.valor, original.tipo, original.fecha)
    assert clave_idempotencia(copia) == clave_idempotencia(original)


# ------------------------------------------------------------------ nodo


def test_el_nodo_responde_ping_y_estado(nodos):
    (nodo,) = nodos(1, hilos=3, cola=5)
    cliente = ClienteNodo(nodo.host, nodo.puerto)
    assert cliente.solicitar({"id": 1, "tipo": "PING"}, 2)["ok"] is True
    estado = cliente.solicitar({"id": 2, "tipo": "ESTADO"}, 2)["estado"]
    assert estado["hilos"] == 3 and estado["capacidad_cola"] == 5 and estado["nombre"] == nodo.nombre
    cliente.cerrar()


def test_el_nodo_rechaza_solicitudes_invalidas(nodos):
    (nodo,) = nodos(1)
    cliente = ClienteNodo(nodo.host, nodo.puerto)
    assert cliente.solicitar({"id": 1, "tipo": "BAILAR"}, 2)["error"] == "SOLICITUD_INVALIDA"
    assert cliente.solicitar({"id": 2, "tipo": "ENVIAR", "clave": "k"}, 2)["error"] == "SOLICITUD_INVALIDA"
    cliente.cerrar()


def test_el_nodo_usa_su_pool_de_hilos_y_no_mas(nodos):
    """Con 2 hilos y 8 solicitudes de 100 ms, el trabajo se hace en 4 tandas, no en una."""
    (nodo,) = nodos(1, hilos=2, cola=16, latencia_ms=100.0)
    cliente = ClienteNodo(nodo.host, nodo.puerto)
    inicio = time.perf_counter()
    with ThreadPoolExecutor(8) as pool:
        respuestas = list(pool.map(
            lambda i: cliente.solicitar(
                {"id": i, "tipo": "ENVIAR", "clave": f"k{i}", "documento": documento_a_dict(documento(i))}, 5),
            range(8)))
    duracion = time.perf_counter() - inicio
    assert all(r["ok"] and r["aceptado"] for r in respuestas)
    assert duracion >= 0.38  # 8 trabajos / 2 hilos * 100 ms
    assert nodo.estado()["procesadas"] == 8
    cliente.cerrar()


def test_el_nodo_aplica_contrapresion_cuando_se_llena(nodos):
    """1 hilo + cola de 1 = cupo para 2; la tercera solicitud simultánea recibe OCUPADO."""
    (nodo,) = nodos(1, hilos=1, cola=1, latencia_ms=300.0)
    cliente = ClienteNodo(nodo.host, nodo.puerto)
    with ThreadPoolExecutor(4) as pool:
        respuestas = list(pool.map(
            lambda i: cliente.solicitar(
                {"id": i, "tipo": "ENVIAR", "clave": f"k{i}", "documento": documento_a_dict(documento(i))}, 5),
            range(4)))
    ocupadas = [r for r in respuestas if not r["ok"] and r["error"] == "OCUPADO"]
    assert len(ocupadas) == 2 and sum(1 for r in respuestas if r["ok"]) == 2
    assert nodo.estado()["saturadas"] == 2
    cliente.cerrar()


def test_el_nodo_es_idempotente(nodos):
    (nodo,) = nodos(1)
    cliente = ClienteNodo(nodo.host, nodo.puerto)
    mensaje = {"id": 1, "tipo": "ENVIAR", "clave": "misma", "documento": documento_a_dict(documento(1))}
    primera = cliente.solicitar(mensaje, 2)
    segunda = cliente.solicitar({**mensaje, "id": 2}, 2)
    assert primera["ok"] and segunda["ok"] and primera["codigo"] == segunda["codigo"]
    estado = nodo.estado()
    assert estado["procesadas"] == 1 and estado["duplicadas"] == 1
    cliente.cerrar()


def test_dos_solicitudes_iguales_a_la_vez_se_procesan_una_sola_vez(nodos):
    (nodo,) = nodos(1, hilos=4, latencia_ms=150.0)
    cliente = ClienteNodo(nodo.host, nodo.puerto)
    mensaje = {"tipo": "ENVIAR", "clave": "simultanea", "documento": documento_a_dict(documento(2))}
    with ThreadPoolExecutor(2) as pool:
        respuestas = list(pool.map(lambda i: cliente.solicitar({**mensaje, "id": i}, 5), (1, 2)))
    assert all(r["ok"] for r in respuestas)
    assert nodo.estado()["procesadas"] == 1
    cliente.cerrar()


# ------------------------------------------------------------------ proxy y mediador


def test_el_proxy_cumple_la_interfaz_del_proveedor(nodos, clusters):
    cluster = clusters(nodos(1))
    respuesta = cluster.proxy.enviar(documento(1))
    assert respuesta.aceptado and respuesta.codigo == "SIM-00" and "[127.0.0.1:" in respuesta.mensaje
    assert "1 nodo" in cluster.proxy.nombre


def test_un_rechazo_del_proveedor_no_se_reintenta(nodos, clusters):
    (nodo,) = nodos(1)
    cluster = clusters([nodo])
    respuesta = cluster.proxy.enviar(documento(1, valor=0))  # SIM-05: valor en cero
    assert not respuesta.aceptado and respuesta.codigo == "SIM-05"
    assert nodo.estado()["procesadas"] == 1  # un solo intento: el rechazo es una respuesta válida


def test_el_mediador_reparte_la_carga_entre_los_nodos(nodos, clusters):
    grupo = nodos(3, hilos=4, latencia_ms=20.0)
    cluster = clusters(grupo)
    with ThreadPoolExecutor(12) as pool:
        respuestas = list(pool.map(lambda i: cluster.proxy.enviar(documento(i)), range(60)))
    assert all(r.aceptado for r in respuestas)
    atendidos = [n.estado()["procesadas"] for n in grupo]
    assert sum(atendidos) == 60 and all(a >= 10 for a in atendidos), atendidos


def test_si_un_nodo_cae_el_proxy_reintenta_en_otro_y_no_se_pierde_nada(nodos, clusters):
    a, b = nodos(2)
    cluster = clusters([a, b])
    assert cluster.proxy.enviar(documento(0)).aceptado  # conexiones calientes en el pool
    a.detener()  # caída del nodo A
    respuestas = [cluster.proxy.enviar(documento(i)) for i in range(1, 21)]
    assert all(r.aceptado for r in respuestas)
    assert b.estado()["procesadas"] >= 20
    cluster.bus.vaciar()
    estados = {e["nodo"]: e for e in cluster.mediador.estado()}
    assert estados[f"{a.host}:{a.puerto}"]["circuito"] == "ABIERTO"
    resumen = cluster.metricas.resumen()
    assert resumen["aceptados"] == 21 and resumen["intentos_fallidos"].get("conexion", 0) >= 1
    assert any(c["estado"] == "ABIERTO" for c in resumen["cambios_de_circuito"])


def test_el_circuito_se_cierra_cuando_el_nodo_vuelve(nodos, clusters):
    a, b = nodos(2)
    cluster = clusters([a, b])
    puerto_a = a.puerto
    a.detener()
    for i in range(10):
        assert cluster.proxy.enviar(documento(i)).aceptado
    nombre_a = f"{a.host}:{puerto_a}"
    assert {e["nodo"]: e["circuito"] for e in cluster.mediador.estado()}[nombre_a] == "ABIERTO"

    NodoProveedor("nodo-1-bis", puerto=puerto_a, latencia_ms=5.0).iniciar()  # el nodo A se recupera
    time.sleep(0.35)  # enfriamiento del circuito
    cluster.mediador.sondear()  # el latido prueba el nodo y cierra el circuito
    assert {e["nodo"]: e["circuito"] for e in cluster.mediador.estado()}[nombre_a] == EstadoCircuito.CERRADO.value


def test_si_ningun_nodo_responde_el_documento_queda_rechazado_para_reintentar(nodos, clusters):
    grupo = nodos(2)
    cluster = clusters(grupo, max_intentos=3)
    for nodo in grupo:
        nodo.detener()
    respuesta = cluster.proxy.enviar(documento(1))
    assert not respuesta.aceptado and respuesta.codigo == "NODOS-01" and "Reintentar" in respuesta.mensaje
    cluster.bus.vaciar()
    assert cluster.metricas.resumen()["sin_respuesta"] == 1


def test_un_nodo_lento_agota_el_tiempo_y_otro_atiende(nodos, clusters):
    lento, rapido = nodos(1, latencia_ms=800.0)[0], nodos(1, latencia_ms=5.0)[0]
    cluster = clusters([lento, rapido], timeout_seg=0.2)
    respuestas = [cluster.proxy.enviar(documento(i)) for i in range(6)]
    assert all(r.aceptado for r in respuestas)
    cluster.bus.vaciar()
    assert cluster.metricas.resumen()["intentos_fallidos"].get("timeout", 0) >= 1


def test_un_nodo_saturado_deriva_el_trabajo_a_otro_sin_abrir_su_circuito(nodos, clusters):
    chico = nodos(1, hilos=1, cola=0, latencia_ms=200.0)[0]
    grande = nodos(1, hilos=8, cola=32, latencia_ms=20.0)[0]
    cluster = clusters([chico, grande], umbral_fallos=2)
    with ThreadPoolExecutor(10) as pool:
        respuestas = list(pool.map(lambda i: cluster.proxy.enviar(documento(i)), range(40)))
    assert all(r.aceptado for r in respuestas)
    estados = {e["nodo"]: e for e in cluster.mediador.estado()}
    assert estados[f"{chico.host}:{chico.puerto}"]["circuito"] == "CERRADO"  # saturado no es caído


def test_un_error_del_nodo_se_reintenta_en_otro(nodos, clusters):
    malo = nodos(1, prob_error=1.0)[0]  # todas sus solicitudes fallan
    bueno = nodos(1)[0]
    cluster = clusters([malo, bueno])
    assert all(cluster.proxy.enviar(documento(i)).aceptado for i in range(10))
    assert bueno.estado()["procesadas"] == 10 and malo.estado()["errores"] >= 1


# ------------------------------------------------------------------ observadores


def test_el_bus_entrega_a_los_observadores_y_aisla_sus_errores():
    bus = BusEventos()
    recibidos = []
    bus.suscribir("x", lambda e: (_ for _ in ()).throw(RuntimeError("observador roto")))
    bus.suscribir("x", lambda e: recibidos.append(e.datos["n"]))
    bus.suscribir("*", lambda e: recibidos.append(f"todos:{e.tipo}"))
    bus.iniciar()
    bus.publicar("x", n=1)
    bus.vaciar()
    bus.detener()
    assert recibidos == [1, "todos:x"]


def test_el_bus_descarta_y_cuenta_si_se_llena_sin_bloquear():
    bus = BusEventos(capacidad=2)  # sin hilo despachador: la cola se llena
    for i in range(5):
        bus.publicar("x", n=i)
    assert bus.descartados == 3


def test_las_metricas_calculan_percentiles():
    bus = BusEventos()
    metricas = Metricas(bus)
    bus.iniciar()
    for ms in range(1, 101):
        bus.publicar("envio.exitoso", nodo="n1", ms=float(ms), intentos=1 if ms % 10 else 2, aceptado=True)
    bus.vaciar()
    bus.detener()
    r = metricas.resumen()
    assert r["documentos"] == 100 and r["reintentos"] == 10 and r["por_nodo"] == {"n1": 100}
    assert r["latencia_ms"]["p50"] == pytest.approx(50.5) and r["latencia_ms"]["max"] == 100.0
    assert r["latencia_ms"]["p95"] > r["latencia_ms"]["p50"]


# ------------------------------------------------------------------ integración con la API


@pytest.fixture
def grupo_de_nodos(nodos):
    return nodos(2, hilos=4, latencia_ms=5.0)


@pytest.fixture
def config(config, grupo_de_nodos):
    """La aplicación factura electrónicamente a través de los nodos."""
    return dataclasses.replace(
        config, dian_obligatoria=True, caja_obligatoria=True,
        nodos_proveedor=tuple(f"{n.host}:{n.puerto}" for n in grupo_de_nodos),
        proxy_timeout_seg=1.0, circuito_enfriamiento_seg=0.3,
    )


def test_la_api_emite_la_factura_electronica_por_medio_de_los_nodos(cliente, recepcion, factura_eps):
    r = cliente.post(f"/api/electronica/facturas/{factura_eps['id']}/emitir", headers=recepcion)
    assert r.status_code == 201, r.text
    doc = r.json()
    assert doc["estado"] == "ACEPTADO" and "[127.0.0.1:" in doc["mensaje_respuesta"]
    assert "nodo" in cliente.get("/api/electronica/proveedor", headers=recepcion).json()["proveedor"].lower()


def test_el_administrador_ve_el_estado_del_cluster(cliente, recepcion, factura_eps):
    cliente.post(f"/api/electronica/facturas/{factura_eps['id']}/emitir", headers=recepcion)
    cliente.app.state.contenedor.cluster.bus.vaciar()
    admin = iniciar_sesion(cliente, "admin")
    r = cliente.get("/api/electronica/nodos", headers=admin)
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["modo"] == "distribuido" and len(cuerpo["nodos"]) == 2
    assert cuerpo["metricas"]["aceptados"] == 1
    assert cliente.get("/api/electronica/nodos", headers=recepcion).status_code == 403
    salud = cliente.get("/health").json()
    assert salud["nodos_facturacion"] == {"total": 2, "disponibles": 2}


def test_sin_nodos_la_factura_queda_rechazada_y_se_reintenta_al_volver(
    cliente, recepcion, factura_eps, grupo_de_nodos
):
    puertos = [n.puerto for n in grupo_de_nodos]
    for nodo in grupo_de_nodos:
        nodo.detener()
    emitida = cliente.post(f"/api/electronica/facturas/{factura_eps['id']}/emitir", headers=recepcion)
    assert emitida.status_code == 201
    doc = emitida.json()
    assert doc["estado"] == "RECHAZADO" and doc["codigo_respuesta"] == "NODOS-01"
    # el consultorio sigue operando: la factura solo espera su transmisión
    assert cliente.get(url(factura_eps), headers=recepcion).status_code == 200

    for puerto in puertos:  # los nodos vuelven a estar en línea
        NodoProveedor("recuperado", puerto=puerto, latencia_ms=5.0).iniciar()
    time.sleep(0.4)
    reintento = cliente.post(f"/api/electronica/documentos/{doc['id']}/reintentar", headers=recepcion)
    assert reintento.status_code == 200, reintento.text
    assert reintento.json()["estado"] == "ACEPTADO" and reintento.json()["numero"] == doc["numero"]


def test_las_emisiones_simultaneas_de_distintas_facturas_son_correctas(cliente, recepcion, factura_eps):
    """Ocho solicitudes simultáneas sobre la misma factura: una se emite, las demás reciben conflicto."""
    with ThreadPoolExecutor(8) as pool:
        codigos = list(pool.map(
            lambda _: cliente.post(f"/api/electronica/facturas/{factura_eps['id']}/emitir", headers=recepcion).status_code,
            range(8)))
    assert codigos.count(201) == 1 and codigos.count(409) == 7
    docs = cliente.get("/api/electronica/documentos", headers=recepcion).json()
    assert len(docs) == 1


def test_los_hilos_de_los_nodos_no_se_acumulan(nodos, clusters):
    """Tras una ráfaga, el número de hilos vivos vuelve a un valor estable (no hay fugas)."""
    grupo = nodos(2, hilos=4, latencia_ms=5.0)
    cluster = clusters(grupo)
    cluster.proxy.enviar(documento(0))
    antes = threading.active_count()
    with ThreadPoolExecutor(16) as pool:
        list(pool.map(lambda i: cluster.proxy.enviar(documento(i + 1)), range(100)))
    time.sleep(0.2)
    assert threading.active_count() - antes <= 24  # los 16 del pool de la prueba, como máximo


def test_el_servicio_no_retiene_el_candado_mientras_transmite(
    cliente, recepcion, medico, usuarios, pacientes, catalogo, convenios, grupo_de_nodos
):
    """Tres facturas distintas con nodos de 250 ms: si el candado cubriera el envío tardarían ~750 ms."""
    facturas = []
    for documento_paciente in ("1000000001", "1000000002", "1000000003"):
        ingreso = admitir(cliente, recepcion, usuarios, pacientes[documento_paciente], convenios["Contributivo"]).json()
        registrar(cliente, medico, ingreso["id"], catalogo["CON-GEN"])
        facturas.append(cliente.post("/api/facturas", json={"ingreso_id": ingreso["id"]}, headers=recepcion).json())
    for nodo in grupo_de_nodos:
        nodo.latencia_ms = 250.0
    inicio = time.perf_counter()
    with ThreadPoolExecutor(3) as pool:
        respuestas = list(pool.map(
            lambda f: cliente.post(f"/api/electronica/facturas/{f['id']}/emitir", headers=recepcion), facturas))
    duracion = time.perf_counter() - inicio
    assert all(r.status_code == 201 and r.json()["estado"] == "ACEPTADO" for r in respuestas)
    assert duracion < 0.6, duracion
    consecutivos = [r.json()["numero"] for r in respuestas]
    assert len(set(consecutivos)) == 3  # numeración sin repetidos aunque se emita en paralelo


def test_si_el_proveedor_lanza_una_excepcion_el_documento_queda_para_reintentar(cliente, recepcion, factura_eps):
    from app.services.dian import RespuestaProveedor

    servicio = cliente.app.state.contenedor.electronica
    real = servicio._proveedor

    class Roto:
        nombre = "roto"

        def enviar(self, documento):
            raise RuntimeError("falla inesperada")

    servicio._proveedor = Roto()
    with pytest.raises(RuntimeError):
        servicio.emitir(factura_eps["id"], None)
    docs = cliente.get("/api/electronica/documentos", headers=recepcion).json()
    assert len(docs) == 1 and docs[0]["estado"] == "RECHAZADO" and docs[0]["codigo_respuesta"] == "ERR-PROVEEDOR"

    servicio._proveedor = real
    reintento = cliente.post(f"/api/electronica/documentos/{docs[0]['id']}/reintentar", headers=recepcion)
    assert reintento.status_code == 200 and reintento.json()["estado"] == "ACEPTADO"
