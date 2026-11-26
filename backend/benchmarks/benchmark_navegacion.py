"""Medición de la navegación del catálogo CIE-10 y de la estructura de rutas (Unidad 3).

Experimentos:
  n1  Latencia de búsqueda: estrategia secuencial frente a índice invertido,
      con el catálogo a distintas escalas (149, 1.000, 5.000, 12.000, 30.000).
  n2  Costo por pulsación: lo que cuesta escribir «diabetes» letra a letra,
      con y sin el retardo (debounce) de 250 ms del frontend.
  n3  Construcción del índice: cuánto tarda en arrancar y cuántas claves ocupa.
  n4  Profundidad de navegación: pasos hasta cada pantalla según el rol,
      leídos de la tabla de rutas del frontend.

Uso (desde la carpeta backend)::

    python benchmarks/benchmark_navegacion.py

Salida: benchmarks/resultados/resultados_navegacion.json
"""
from __future__ import annotations

import json
import random
import re
import statistics
import sys
import time
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent))

from app.data.cie10 import CIE10  # noqa: E402
from app.services.busqueda import BusquedaIndiceInvertido, BusquedaSecuencial  # noqa: E402

RESULTADOS = AQUI / "resultados"
RESULTADOS.mkdir(exist_ok=True)

CONSULTAS = [
    "diabetes", "hipertension", "a09", "infeccion urinaria", "lumbago",
    "faringitis aguda", "e11", "control", "cefalea", "anemia",
    "embarazo", "asma", "gastritis", "j00", "dolor abdominal",
]

# Palabras tomadas de las descripciones reales, para construir catálogos sintéticos
# que conserven el vocabulario clínico (y por tanto el comportamiento del índice).
PALABRAS = sorted({p for _, d in CIE10 for p in re.findall(r"[A-Za-zÁÉÍÓÚáéíóúñÑ]{4,}", d)})
LETRAS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def catalogo_escalado(n: int, semilla: int = 7) -> list[tuple[str, str]]:
    """Catálogo de n entradas: las reales primero y el resto generadas con el mismo vocabulario."""
    azar = random.Random(semilla)
    salida = list(CIE10[:n])
    vistos = {c for c, _ in salida}
    while len(salida) < n:
        codigo = f"{azar.choice(LETRAS)}{azar.randint(0, 99):02d}{azar.randint(0, 9)}"
        if codigo in vistos:
            continue
        vistos.add(codigo)
        descripcion = " ".join(azar.sample(PALABRAS, azar.randint(3, 7)))
        salida.append((codigo, descripcion))
    return salida


def medir(funcion, repeticiones: int) -> dict:
    muestras = []
    for _ in range(repeticiones):
        inicio = time.perf_counter()
        funcion()
        muestras.append((time.perf_counter() - inicio) * 1000)
    muestras.sort()
    return {
        "p50_ms": round(statistics.median(muestras), 3),
        "p95_ms": round(muestras[int(len(muestras) * 0.95) - 1], 3),
        "media_ms": round(statistics.fmean(muestras), 3),
        "muestras": len(muestras),
    }


def e1_latencia() -> list[dict]:
    """n1: latencia de una consulta completa (primeros 20 resultados) por estrategia y escala.

    Las repeticiones bajan con la escala: con catálogos grandes cada repetición ya
    agrega decenas de consultas, suficientes para una mediana estable.
    """
    filas = []
    for n in (149, 1_000, 5_000, 12_000):
        catalogo = catalogo_escalado(n)
        for clase in (BusquedaSecuencial, BusquedaIndiceInvertido):
            estrategia = clase(catalogo)

            def consulta_completa(e=estrategia):
                for q in CONSULTAS:
                    sorted(e.buscar(q), key=lambda t: (t[0], t[1]))[:20]

            repeticiones = max(3, min(20, int(60_000 / n)))
            tiempos = medir(consulta_completa, repeticiones)
            por_consulta = {k: round(v / len(CONSULTAS), 3) for k, v in tiempos.items() if k.endswith("_ms")}
            filas.append({"n": n, "estrategia": clase.nombre, **por_consulta})
            print(f"  n1 n={n:>6} {clase.nombre:<11} p50={por_consulta['p50_ms']:>8.3f} ms/consulta")
    return filas


def e2_pulsaciones() -> list[dict]:
    """n2: escribir «diabetes» (8 pulsaciones) con y sin el retardo de 250 ms del frontend."""
    filas = []
    palabra = "diabetes"
    prefijos = [palabra[: i + 1] for i in range(len(palabra))]
    for n in (12_000,):
        catalogo = catalogo_escalado(n)
        for clase in (BusquedaSecuencial, BusquedaIndiceInvertido):
            estrategia = clase(catalogo)
            # Sin debounce: una consulta por pulsación. Con debounce: solo la última.
            sin_debounce = medir(lambda e=estrategia: [sorted(e.buscar(p))[:20] for p in prefijos], 10)
            con_debounce = medir(lambda e=estrategia: sorted(e.buscar(palabra))[:20], 10)
            filas.append({
                "n": n,
                "estrategia": clase.nombre,
                "pulsaciones": len(prefijos),
                "sin_debounce_p50_ms": sin_debounce["p50_ms"],
                "con_debounce_p50_ms": con_debounce["p50_ms"],
            })
            print(f"  n2 {clase.nombre:<11} sin debounce={sin_debounce['p50_ms']:>8.3f} ms  con debounce={con_debounce['p50_ms']:>7.3f} ms")
    return filas


def e3_construccion() -> list[dict]:
    """n3: costo de arranque y tamaño del índice."""
    filas = []
    for n in (149, 1_000, 5_000, 12_000):
        catalogo = catalogo_escalado(n)
        tiempos = medir(lambda c=catalogo: BusquedaIndiceInvertido(c), 3)
        indice = BusquedaIndiceInvertido(catalogo)
        filas.append({"n": n, "construccion_p50_ms": tiempos["p50_ms"], "claves": indice.tamano_indice})
        print(f"  n3 n={n:>6} construccion={tiempos['p50_ms']:>8.2f} ms  claves={indice.tamano_indice}")
    return filas


RUTAS_JS = AQUI.parent.parent / "frontend" / "js" / "app.js"


def e4_profundidad() -> dict:
    """n4: pantallas visibles y pasos hasta cada una, por rol, leídos de la tabla de rutas."""
    texto = RUTAS_JS.read_text(encoding="utf-8")
    bloque = texto.split("const RUTAS = {", 1)[1].split("\n};", 1)[0]
    rutas = {}
    for linea in bloque.splitlines():
        m = re.match(r'\s*"?([a-z-]+)"?:\s*\{(.*)\},?\s*$', linea)
        if not m:
            continue
        nombre, cuerpo = m.group(1), m.group(2)
        roles = re.findall(r'"([A-Z]+)"', cuerpo.split("roles:", 1)[1].split("]", 1)[0]) if "roles:" in cuerpo else []
        rutas[nombre] = {
            "roles": roles,
            "oculta": "oculta: true" in cuerpo,
            "padre": (re.search(r'padre:\s*"([a-z-]+)"', cuerpo) or [None, None])[1],
        }
    resumen = {}
    for rol in ("RECEPCION", "MEDICO", "ADMINISTRADOR", "LABORATORIO"):
        visibles = [n for n, r in rutas.items() if rol in r["roles"] and not r["oculta"]]
        anidadas = [n for n, r in rutas.items() if rol in r["roles"] and r["oculta"]]
        total = len(visibles) + len(anidadas)
        pasos = len(visibles) * 1 + len(anidadas) * 2  # menú = 1 paso; pantalla hija = 2
        resumen[rol] = {
            "pantallas_totales": total,
            "en_menu": len(visibles),
            "anidadas": len(anidadas),
            "pasos_promedio": round(pasos / total, 2) if total else 0,
            "pasos_maximo": 2 if anidadas else 1,
            "ocultas_por_rol": len(rutas) - total,
        }
        print(f"  n4 {rol:<14} menú={len(visibles):>2}  anidadas={len(anidadas)}  pasos≤{resumen[rol]['pasos_maximo']}  ocultas={resumen[rol]['ocultas_por_rol']}")
    resumen["_rutas_declaradas"] = len(rutas)
    return resumen


def main() -> None:
    print("Catálogo real:", len(CIE10), "códigos ·", len(PALABRAS), "palabras de vocabulario")
    salida = {
        "n1_latencia": e1_latencia(),
        "n2_pulsaciones": e2_pulsaciones(),
        "n3_construccion": e3_construccion(),
        "n4_profundidad": e4_profundidad(),
        "consultas": CONSULTAS,
    }
    destino = RESULTADOS / "resultados_navegacion.json"
    destino.write_text(json.dumps(salida, indent=1, ensure_ascii=False), encoding="utf-8")
    print("\nResultados:", destino)


if __name__ == "__main__":
    main()
