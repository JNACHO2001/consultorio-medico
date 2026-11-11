"""Gráficas (a color) de la evaluación distribuida, a partir de resultados/resultados_distribuido.json.

    python backend/benchmarks/graficas.py

Salida: docs/informe/img/g1_horizontal.png ... g5_servicio.png
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parents[1]
SALIDA = RAIZ / "docs" / "informe" / "img"
SALIDA.mkdir(parents=True, exist_ok=True)
datos = json.loads((AQUI / "resultados" / "resultados_distribuido.json").read_text(encoding="utf-8"))

AZUL, NARANJA, VERDE, ROJO, MORADO, GRIS = "#1F5FA8", "#C45A00", "#2E7D32", "#B3261E", "#6A3FA0", "#777777"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.alpha": 0.25})


def guardar(fig, nombre: str) -> None:
    fig.savefig(SALIDA / nombre, dpi=170, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def g1() -> None:
    filas = datos["e1_horizontal"]["filas"]
    nodos = [f["nodos"] for f in filas]
    fig, ax = plt.subplots(figsize=(6.4, 3.8))
    barras = ax.bar([str(n) for n in nodos], [f["docs_por_s_media"] for f in filas], color=AZUL, width=0.55,
                    yerr=[f["docs_por_s_desv"] for f in filas], capsize=4, label="Medido (media ± desv.)")
    ideal = [filas[0]["docs_por_s_media"] * n for n in nodos]
    ax.plot([str(n) for n in nodos], ideal, color=NARANJA, marker="o", linestyle="--", label="Escalado lineal ideal")
    for b, f in zip(barras, filas):
        ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 12, f"{f['docs_por_s_media']:.0f}\n({f['eficiencia_pct']:.0f} %)",
                ha="center", fontsize=9)
    ax.set_xlabel("Número de nodos (4 hilos cada uno)")
    ax.set_ylabel("Documentos por segundo")
    ax.set_title("Escalabilidad horizontal", fontweight="bold")
    ax.set_ylim(0, max(ideal) * 1.2)
    ax.legend(frameon=False, loc="upper left")
    guardar(fig, "g1_horizontal.png")


def g2() -> None:
    filas = datos["e2_vertical"]["filas"]
    hilos = [f["hilos_por_nodo"] for f in filas]
    fig, ax = plt.subplots(figsize=(6.4, 3.8))
    ax.plot(hilos, [f["capacidad_teorica"] for f in filas], color=NARANJA, linestyle="--", marker="o",
            label="Capacidad teórica (hilos / 40 ms)")
    ax.errorbar(hilos, [f["docs_por_s_media"] for f in filas], yerr=[f["docs_por_s_desv"] for f in filas], color=AZUL,
                marker="s", capsize=4, linewidth=2, label="Medido")
    ax.set_xscale("log", base=2)
    ax.set_xticks(hilos)
    ax.set_xticklabels([str(h) for h in hilos])
    ax.set_xlabel("Hilos por nodo (1 nodo)")
    ax.set_ylabel("Documentos por segundo")
    ax.set_title("Escalabilidad vertical: más hilos en un nodo", fontweight="bold")
    ax.legend(frameon=False)
    guardar(fig, "g2_vertical.png")


def g3() -> None:
    d = datos["e3_saturacion"]
    nombres = {"cola_corta": "Cola corta\n(2 hilos, cola 1)", "cola_ajustada": "Cola ajustada\n(2 hilos, cola 32)"}
    fig, ejes = plt.subplots(1, 3, figsize=(9.6, 3.6))
    claves = ["cola_corta", "cola_ajustada"]
    colores = [ROJO, VERDE]
    metricas = [("tasa_exito_pct", "Éxito (%)"), ("p95_ms", "Latencia p95 (ms)"), ("reintentos", "Reintentos (3 corridas)")]
    for ax, (clave, titulo) in zip(ejes, metricas):
        valores = [d[k][clave] for k in claves]
        barras = ax.bar([nombres[k] for k in claves], valores, color=colores, width=0.55)
        for b, v in zip(barras, valores):
            ax.text(b.get_x() + b.get_width() / 2, b.get_height(), f"{v:g}", ha="center", va="bottom", fontsize=9)
        ax.set_title(titulo, fontsize=10, fontweight="bold")
        ax.tick_params(axis="x", labelsize=8)
        ax.set_ylim(0, max(valores) * 1.25 if max(valores) else 1)
    fig.suptitle("Saturación: efecto del tamaño de la cola de admisión (2 nodos, 64 clientes)", fontweight="bold", y=1.03)
    guardar(fig, "g3_saturacion.png")


def g4() -> None:
    d = datos["e4_robustez"]
    serie = d["serie"]
    t = [s["t"] for s in serie]
    fig, ax = plt.subplots(figsize=(8.2, 4.0))
    ax.axvspan(d["t_caida_s"], d["t_regreso_s"], color=ROJO, alpha=0.12, label="Nodo-2 caído (SIGKILL)")
    ax.bar(t, [s["docs"] for s in serie], width=0.8, align="edge", color=AZUL, label="Documentos por segundo")
    ax.set_xlabel("Tiempo (s)")
    ax.set_ylabel("Documentos por segundo", color=AZUL)
    ax2 = ax.twinx()
    ax2.plot([x + 0.5 for x in t], [s["p95_ms"] for s in serie], color=NARANJA, marker="o", label="Latencia p95 (ms)")
    ax2.set_ylabel("Latencia p95 (ms)", color=NARANJA)
    ax2.spines["right"].set_visible(True)
    ax2.grid(False)
    ax.axvline(d["t_caida_s"], color=ROJO, linestyle="--")
    ax.axvline(d["t_regreso_s"], color=VERDE, linestyle="--")
    ax.text(d["t_caida_s"] + 0.1, ax.get_ylim()[1] * 0.96, "cae nodo-2", color=ROJO, fontsize=9, va="top")
    ax.text(d["t_regreso_s"] + 0.1, ax.get_ylim()[1] * 0.96, "vuelve nodo-2", color=VERDE, fontsize=9, va="top")
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, frameon=False, loc="lower right", fontsize=8)
    ax.set_title(f"Robustez: tasa de éxito {d['global']['tasa_exito_pct']} % durante toda la prueba", fontweight="bold")
    guardar(fig, "g4_robustez.png")


def g5() -> None:
    antes, despues = datos["e5_servicio_antes"]["filas"], datos["e5_servicio_despues"]["filas"]
    fig, ax = plt.subplots(figsize=(6.4, 3.8))
    anchura = 0.36
    x = range(len(antes))
    b1 = ax.bar([i - anchura / 2 for i in x], [f["docs_por_s"] for f in antes], anchura, color=ROJO,
                label="Antes: candado durante el envío")
    b2 = ax.bar([i + anchura / 2 for i in x], [f["docs_por_s"] for f in despues], anchura, color=VERDE,
                label="Después: candado solo para reservar")
    for barras in (b1, b2):
        for b in barras:
            ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 4, f"{b.get_height():.0f}", ha="center", fontsize=9)
    ax.set_xticks(list(x))
    ax.set_xticklabels([f"{f['nodos']} nodo(s)" for f in antes])
    ax.set_ylabel("Facturas por segundo")
    ax.set_title("Servicio completo: el ajuste del candado", fontweight="bold")
    ax.set_ylim(0, max(f["docs_por_s"] for f in despues) * 1.18)
    ax.legend(frameon=False, loc="upper left")
    guardar(fig, "g5_servicio.png")


if __name__ == "__main__":
    for nombre, funcion in (("e1_horizontal", g1), ("e2_vertical", g2), ("e3_saturacion", g3), ("e4_robustez", g4)):
        if nombre in datos:
            funcion()
    if "e5_servicio_antes" in datos and "e5_servicio_despues" in datos:
        g5()
    print("Gráficas en", SALIDA)
