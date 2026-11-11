"""Evaluación de escalabilidad y robustez de la facturación electrónica distribuida (Unidad 2).

Cada nodo es un **proceso del sistema operativo** con su pool de hilos; el proxy corre en este proceso.
La latencia de 40 ms por documento representa la firma y la transmisión al proveedor (espera de red).

Experimentos:
  e1  Escalabilidad horizontal: 1, 2 y 4 nodos con 4 hilos cada uno.
  e2  Escalabilidad vertical: 1 nodo con 1, 2, 4, 8 y 16 hilos.
  e3  Saturación y contrapresión: cola corta frente a cola ajustada.
  e4  Robustez: un nodo muere (SIGKILL) en plena carga y luego se recupera.
  e5  Servicio completo (FacturacionElectronicaService): efecto del bloqueo durante el envío.

Uso (desde la carpeta backend)::

    python benchmarks/benchmark_distribuido.py --experimentos e1,e2,e3,e4
    python benchmarks/benchmark_distribuido.py --experimentos e5 --etiqueta antes     # código original
    python benchmarks/benchmark_distribuido.py --experimentos e5 --etiqueta despues   # código ajustado

Los resultados se combinan en benchmarks/resultados/resultados_distribuido.json.
"""
from __future__ import annotations

import argparse
import dataclasses
import itertools
import json
import statistics
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.distribuido import ClusterLocal, ClusterProveedor  # noqa: E402
from app.domain.modelos import DocumentoElectronico, TipoDocumentoElectronico  # noqa: E402

SALIDA = Path(__file__).resolve().parent / "resultados" / "resultados_distribuido.json"
LATENCIA_MS = 40.0
_numeros = itertools.count(1)


def documento() -> DocumentoElectronico:
    n = next(_numeros)
    return DocumentoElectronico(
        factura_id=n, tipo=TipoDocumentoElectronico.FACTURA, prefijo="SETP", consecutivo=990_000_000 + n,
        fecha=datetime.now() - timedelta(days=1), adquirente_tipo_documento="31", adquirente_documento="800000001",
        adquirente_dv="1", adquirente_nombre="EPS Demo", adquirente_es_pagador=True, valor_bruto=85_500, valor=85_500,
        cufe=f"{n:096x}", xml="<Invoice>" + "<Linea>0123456789</Linea>" * 40 + "</Invoice>",
    )


def percentil(valores: list[float], p: float) -> float:
    if not valores:
        return 0.0
    ordenados = sorted(valores)
    pos = (len(ordenados) - 1) * p
    i = int(pos)
    j = min(i + 1, len(ordenados) - 1)
    return ordenados[i] + (ordenados[j] - ordenados[i]) * (pos - i)


def resumir(latencias: list[float], aceptados: int, total: int, duracion: float) -> dict:
    return {
        "documentos": total,
        "aceptados": aceptados,
        "tasa_exito_pct": round(100 * aceptados / total, 2) if total else 0.0,
        "duracion_s": round(duracion, 3),
        "docs_por_s": round(total / duracion, 1) if duracion else 0.0,
        "p50_ms": round(percentil(latencias, 0.50), 1),
        "p95_ms": round(percentil(latencias, 0.95), 1),
        "p99_ms": round(percentil(latencias, 0.99), 1),
        "max_ms": round(max(latencias), 1) if latencias else 0.0,
    }


def carga(cluster: ClusterProveedor, total: int, concurrencia: int) -> dict:
    """Envía ``total`` documentos con ``concurrencia`` clientes simultáneos y mide."""
    def una(_: int) -> tuple[float, bool]:
        inicio = time.perf_counter()
        respuesta = cluster.proxy.enviar(documento())
        return (time.perf_counter() - inicio) * 1000, respuesta.aceptado

    for _ in range(concurrencia):  # calentamiento: abre las conexiones del pool
        cluster.proxy.enviar(documento())
    cluster.bus.vaciar()
    cluster.metricas.reiniciar()
    inicio = time.perf_counter()
    with ThreadPoolExecutor(concurrencia) as pool:
        resultados = list(pool.map(una, range(total)))
    duracion = time.perf_counter() - inicio
    cluster.bus.vaciar()
    datos = resumir([r[0] for r in resultados], sum(1 for r in resultados if r[1]), total, duracion)
    resumen = cluster.metricas.resumen()
    datos["reintentos"] = resumen["reintentos"]
    datos["intentos_fallidos"] = resumen["intentos_fallidos"]
    datos["por_nodo"] = resumen["por_nodo"]
    return datos


def con_cluster(n_nodos: int, hilos: int, cola: int, **opciones_cluster):
    nodos = ClusterLocal(n_nodos, hilos=hilos, cola=cola, latencia_ms=LATENCIA_MS)
    return nodos, opciones_cluster


def ejecutar(n_nodos: int, hilos: int, cola: int, total: int, concurrencia: int, repeticiones: int = 3,
             **opciones_cluster) -> dict:
    corridas = []
    with ClusterLocal(n_nodos, hilos=hilos, cola=cola, latencia_ms=LATENCIA_MS) as nodos:
        cluster = ClusterProveedor(nodos.destinos, intervalo_latido_seg=3600, **opciones_cluster)
        cluster.iniciar()
        try:
            for _ in range(repeticiones):
                corridas.append(carga(cluster, total, concurrencia))
        finally:
            cluster.detener()
    rendimientos = [c["docs_por_s"] for c in corridas]
    return {
        "nodos": n_nodos, "hilos_por_nodo": hilos, "cola": cola, "concurrencia": concurrencia,
        "docs_por_s_media": round(statistics.mean(rendimientos), 1),
        "docs_por_s_desv": round(statistics.pstdev(rendimientos), 1),
        "p50_ms": round(statistics.mean(c["p50_ms"] for c in corridas), 1),
        "p95_ms": round(statistics.mean(c["p95_ms"] for c in corridas), 1),
        "p99_ms": round(statistics.mean(c["p99_ms"] for c in corridas), 1),
        "tasa_exito_pct": round(statistics.mean(c["tasa_exito_pct"] for c in corridas), 2),
        "reintentos": sum(c["reintentos"] for c in corridas),
        "intentos_fallidos": corridas[-1]["intentos_fallidos"],
        "por_nodo": corridas[-1]["por_nodo"],
        "corridas": corridas,
    }


# ---------------------------------------------------------------------------------- experimentos


def e1_horizontal() -> dict:
    print("e1: escalabilidad horizontal")
    filas = []
    for n in (1, 2, 4):
        fila = ejecutar(n, hilos=4, cola=64, total=600, concurrencia=64, timeout_seg=10.0)
        print(f"  {n} nodo(s): {fila['docs_por_s_media']} docs/s  p95={fila['p95_ms']} ms  éxito={fila['tasa_exito_pct']}%")
        filas.append(fila)
    base = filas[0]["docs_por_s_media"]
    for fila in filas:
        fila["aceleracion"] = round(fila["docs_por_s_media"] / base, 2)
        fila["eficiencia_pct"] = round(100 * fila["aceleracion"] / fila["nodos"], 1)
    return {"filas": filas, "capacidad_teorica_por_nodo": round(4 / (LATENCIA_MS / 1000), 1)}


def e2_vertical() -> dict:
    print("e2: escalabilidad vertical (hilos por nodo)")
    filas = []
    for hilos in (1, 2, 4, 8, 16):
        fila = ejecutar(1, hilos=hilos, cola=128, total=400, concurrencia=64, timeout_seg=15.0)
        fila["capacidad_teorica"] = round(hilos / (LATENCIA_MS / 1000), 1)
        print(f"  {hilos:>2} hilos: {fila['docs_por_s_media']} docs/s (teórico {fila['capacidad_teorica']})  p95={fila['p95_ms']} ms")
        filas.append(fila)
    return {"filas": filas}


def e3_saturacion() -> dict:
    print("e3: saturación y contrapresión")
    escenarios = {
        "cola_corta": dict(hilos=2, cola=1),
        "cola_ajustada": dict(hilos=2, cola=32),
    }
    filas = {}
    for nombre, cfg in escenarios.items():
        fila = ejecutar(2, total=500, concurrencia=64, timeout_seg=5.0, max_intentos=4, **cfg)
        filas[nombre] = fila
        print(f"  {nombre}: éxito={fila['tasa_exito_pct']}%  {fila['docs_por_s_media']} docs/s  p95={fila['p95_ms']} ms  "
              f"reintentos={fila['reintentos']}  fallidos={fila['intentos_fallidos']}")
    return filas


def e4_robustez() -> dict:
    print("e4: robustez (muere un nodo en plena carga)")
    duracion, t_caida, t_regreso, concurrencia = 18.0, 5.0, 11.0, 12
    registros: list[tuple[float, float, bool]] = []  # (t_fin, ms, aceptado)
    bloqueo = threading.Lock()
    with ClusterLocal(3, hilos=4, cola=32, latencia_ms=LATENCIA_MS) as nodos:
        cluster = ClusterProveedor(nodos.destinos, timeout_seg=3.0, umbral_fallos=3, enfriamiento_seg=1.0,
                                   intervalo_latido_seg=0.5)
        cluster.iniciar()
        for _ in range(12):
            cluster.proxy.enviar(documento())
        cluster.bus.vaciar()
        cluster.metricas.reiniciar()
        t0 = time.perf_counter()
        fin = t0 + duracion

        def cliente() -> None:
            while time.perf_counter() < fin:
                inicio = time.perf_counter()
                aceptado = cluster.proxy.enviar(documento()).aceptado
                ahora = time.perf_counter()
                with bloqueo:
                    registros.append((ahora - t0, (ahora - inicio) * 1000, aceptado))

        marcas: dict[str, float] = {}

        def caos() -> None:
            time.sleep(t_caida)
            marcas["caida"] = time.perf_counter() - t0
            nodos.nodos[1].matar()  # caída abrupta (SIGKILL) de nodo-2
            time.sleep(t_regreso - t_caida)
            nodos.nodos[1].iniciar()  # el nodo vuelve en el mismo puerto
            marcas["regreso"] = time.perf_counter() - t0

        hilos = [threading.Thread(target=cliente) for _ in range(concurrencia)] + [threading.Thread(target=caos)]
        for h in hilos:
            h.start()
        for h in hilos:
            h.join()
        cluster.bus.vaciar()
        resumen = cluster.metricas.resumen()
        t0_reloj = time.time() - (time.perf_counter() - t0)
        circuitos = [{"nodo": c["nodo"], "estado": c["estado"], "t": round(c["momento"] - t0_reloj, 2)}
                     for c in cluster.metricas.resumen(circuitos=100)["cambios_de_circuito"]]
        nombre_caido = f"{nodos.destinos[1][0]}:{nodos.destinos[1][1]}"
        del_caido = [c for c in circuitos if c["nodo"] == nombre_caido]
        abierto = next((c["t"] for c in del_caido if c["estado"] == "ABIERTO" and c["t"] >= marcas["caida"]), None)
        cerrado = next((c["t"] for c in del_caido if c["estado"] == "CERRADO" and c["t"] >= marcas["regreso"] - 0.5), None)
        estado_final = cluster.mediador.estado()
        cluster.detener()

    segundos = []
    for s in range(int(duracion)):
        del_segundo = [r for r in registros if s <= r[0] < s + 1]
        segundos.append({
            "t": s, "docs": len(del_segundo),
            "p95_ms": round(percentil([r[1] for r in del_segundo], 0.95), 1),
            "fallidos": sum(1 for r in del_segundo if not r[2]),
        })

    def media(a: float, b: float) -> float:
        tramo = [x["docs"] for x in segundos if a <= x["t"] < b]
        return round(statistics.mean(tramo), 1) if tramo else 0.0

    total = len(registros)
    aceptados = sum(1 for r in registros if r[2])
    datos = {
        "duracion_s": duracion, "t_caida_s": t_caida, "t_regreso_s": t_regreso, "concurrencia": concurrencia,
        "caida_real_s": round(marcas["caida"], 2), "regreso_real_s": round(marcas["regreso"], 2),
        "deteccion_s": round(abierto - marcas["caida"], 2) if abierto is not None else None,
        "recuperacion_s": round(cerrado - marcas["regreso"], 2) if cerrado is not None else None,
        "global": resumir([r[1] for r in registros], aceptados, total, duracion),
        "docs_por_s_antes": media(1, t_caida), "docs_por_s_con_caida": media(t_caida + 1, t_regreso),
        "docs_por_s_despues": media(t_regreso + 2, duracion),
        "reintentos": resumen["reintentos"], "intentos_fallidos": resumen["intentos_fallidos"],
        "por_nodo": resumen["por_nodo"], "cambios_de_circuito": circuitos, "estado_final": estado_final,
        "serie": segundos,
    }
    g = datos["global"]
    print(f"  {total} documentos, éxito={g['tasa_exito_pct']}%  p99={g['p99_ms']} ms  max={g['max_ms']} ms")
    print(f"  docs/s: antes={datos['docs_por_s_antes']}  con caída={datos['docs_por_s_con_caida']}  "
          f"tras recuperar={datos['docs_por_s_despues']}  reintentos={datos['reintentos']}")
    return datos


def e5_servicio(etiqueta: str) -> dict:
    """Emisiones simultáneas a través de FacturacionElectronicaService (con su candado interno)."""
    print(f"e5: servicio completo ({etiqueta})")
    from fastapi.testclient import TestClient

    from app.config import cargar_configuracion
    from app.main import crear_app

    facturas_total, concurrencia = 96, 16
    filas = []
    for n_nodos in (1, 4):
        with ClusterLocal(n_nodos, hilos=4, cola=64, latencia_ms=LATENCIA_MS) as nodos:
            config = dataclasses.replace(
                cargar_configuracion(), secret_key="clave-solo-para-medir-0123456789-abcdef", iteraciones_hash=1000,
                recordatorios_automaticos=False, dian_obligatoria=False, caja_obligatoria=False,
                nodos_proveedor=tuple(f"{h}:{p}" for h, p in nodos.destinos), proxy_timeout_seg=10.0,
            )
            app = crear_app(config)
            with TestClient(app) as cliente:
                c = app.state.contenedor

                def sesion(usuario: str) -> dict:
                    r = cliente.post("/api/auth/login", json={"usuario": usuario, "contrasena": config.contrasena_demo})
                    return {"Authorization": f"Bearer {r.json()['access_token']}"}

                recepcion, medico, admin = sesion("recepcion1"), sesion("dr.perez"), sesion("admin")
                medico_id = {u["nombre_usuario"]: u["id"] for u in cliente.get("/api/usuarios", headers=admin).json()}["dr.perez"]
                proc = next(p for p in cliente.get("/api/procedimientos", headers=recepcion).json() if p["codigo"] == "CON-GEN")
                facturas = []
                for i in range(facturas_total):
                    paciente = c.pacientes.registrar_paciente(
                        tipo_documento="CC", numero_documento=f"{2_000_000_000 + i}", nombres="Paciente", apellidos=f"Carga {i}",
                        fecha_nacimiento=datetime(1990, 1, 1).date(), sexo="F", telefono="3000000000", correo="", eps="EPS Demo",
                        alergias="")
                    ing = cliente.post("/api/ingresos", json={"paciente_id": paciente.id, "medico_id": medico_id,
                                                              "tipo": "AMBULATORIO", "motivo": "Carga"}, headers=recepcion).json()
                    cliente.post(f"/api/ingresos/{ing['id']}/procedimientos",
                                 json={"procedimiento_id": proc["id"], "cantidad": 1}, headers=medico)
                    facturas.append(cliente.post("/api/facturas", json={"ingreso_id": ing["id"]}, headers=recepcion).json()["id"])
                usuario = c.repo_usuarios.obtener_por_nombre_usuario("recepcion1")
                c.electronica.emitir(facturas[0], usuario)  # calentamiento
                c.cluster.bus.vaciar()

                latencias: list[float] = []

                def emitir(fid: int) -> bool:
                    inicio = time.perf_counter()
                    doc = c.electronica.emitir(fid, usuario)
                    latencias.append((time.perf_counter() - inicio) * 1000)
                    return doc.estado.value == "ACEPTADO"

                inicio = time.perf_counter()
                with ThreadPoolExecutor(concurrencia) as pool:
                    ok = list(pool.map(emitir, facturas[1:]))
                duracion = time.perf_counter() - inicio
                consecutivos = [d.consecutivo for d in c.repo_documentos.listar()]
                fila = {
                    "nodos": n_nodos, **resumir(latencias, sum(ok), len(ok), duracion),
                    "consecutivos_unicos": len(set(consecutivos)) == len(consecutivos),
                }
                print(f"  {n_nodos} nodo(s): {fila['docs_por_s']} facturas/s  p95={fila['p95_ms']} ms  "
                      f"éxito={fila['tasa_exito_pct']}%  consecutivos únicos={fila['consecutivos_unicos']}")
                filas.append(fila)
    return {"concurrencia": concurrencia, "filas": filas}


def main() -> None:
    global LATENCIA_MS
    analizador = argparse.ArgumentParser()
    analizador.add_argument("--experimentos", default="e1,e2,e3,e4")
    analizador.add_argument("--etiqueta", default="", help="para e5: antes | despues")
    analizador.add_argument("--latencia-ms", type=float, default=LATENCIA_MS, help="latencia simulada del proveedor")
    a = analizador.parse_args()
    LATENCIA_MS = a.latencia_ms

    existentes = json.loads(SALIDA.read_text(encoding="utf-8")) if SALIDA.exists() else {}
    existentes["entorno"] = {
        "fecha": datetime.now().isoformat(timespec="seconds"), "nucleos": __import__("os").cpu_count(),
        "python": sys.version.split()[0], "latencia_simulada_ms": 40.0,
    }
    for nombre in a.experimentos.split(","):
        if nombre == "e1":
            existentes["e1_horizontal"] = e1_horizontal()
        elif nombre == "e2":
            existentes["e2_vertical"] = e2_vertical()
        elif nombre == "e3":
            existentes["e3_saturacion"] = e3_saturacion()
        elif nombre == "e4":
            existentes["e4_robustez"] = e4_robustez()
        elif nombre == "e5":
            existentes[f"e5_servicio_{a.etiqueta or 'actual'}"] = e5_servicio(a.etiqueta or "actual")
        SALIDA.parent.mkdir(parents=True, exist_ok=True)
        SALIDA.write_text(json.dumps(existentes, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Resultados en {SALIDA}")


if __name__ == "__main__":
    main()
