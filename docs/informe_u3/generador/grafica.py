"""Figura 5 del informe de la Unidad 3: latencia por consulta frente al tamaño del catálogo.

En blanco y negro, para que el informe impreso se lea igual que en pantalla.

    python docs/informe_u3/generador/grafica.py
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402

AQUI = Path(__file__).resolve().parent
DESTINO = AQUI.parent / "img"
DESTINO.mkdir(parents=True, exist_ok=True)
DATOS = AQUI.parents[2] / "backend" / "benchmarks" / "resultados" / "resultados_navegacion.json"

R = json.loads(DATOS.read_text(encoding="utf-8"))
filas = R["n1_latencia"]
sec = [f for f in filas if f["estrategia"] == "secuencial"]
idx = [f for f in filas if f["estrategia"] == "indice"]

fig, ax = plt.subplots(figsize=(8.4, 4.6))
ax.plot([f["n"] for f in sec], [f["p50_ms"] for f in sec], marker="o", color="black",
        linewidth=1.8, markersize=6, markerfacecolor="white", markeredgewidth=1.5,
        label="Búsqueda secuencial (recorre el catálogo)")
ax.plot([f["n"] for f in idx], [f["p50_ms"] for f in idx], marker="s", color="black",
        linewidth=1.8, markersize=5.5, linestyle="--", markerfacecolor="black",
        label="Índice invertido (intersección de listas)")

ax.axhline(100, color="#666666", linewidth=1.1, linestyle=(0, (2, 3)))
ax.text(170, 118, "100 ms · umbral de respuesta inmediata", fontsize=8.6, color="#444444")

ax.set_xscale("log")
ax.set_yscale("log")
ax.set_xlabel("Códigos en el catálogo", fontsize=10)
ax.set_ylabel("Latencia por consulta (ms, mediana)", fontsize=10)
ax.set_xticks([f["n"] for f in sec])
ax.get_xaxis().set_major_formatter(FuncFormatter(lambda v, _: f"{int(v):,}".replace(",", ".")))
ax.get_yaxis().set_major_formatter(FuncFormatter(
    lambda v, _: ("%g" % v) if v >= 1 else ("%.2f" % v).rstrip("0").rstrip(".")))
ax.tick_params(labelsize=9)
ax.grid(True, which="major", color="#DDDDDD", linewidth=0.8)
ax.grid(True, which="minor", color="#F0F0F0", linewidth=0.5)
ax.set_axisbelow(True)
for lado in ("top", "right"):
    ax.spines[lado].set_visible(False)
ax.legend(fontsize=9, frameon=False, loc="upper left")

# anotar la distancia en el punto del catálogo oficial
i = next(k for k, f in enumerate(sec) if f["n"] == 12_000)
ax.annotate(
    f"{sec[i]['p50_ms'] / idx[i]['p50_ms']:,.0f} ×".replace(",", "."),
    xy=(12_000, (sec[i]["p50_ms"] * idx[i]["p50_ms"]) ** 0.5),
    fontsize=10, ha="center", va="center",
    bbox=dict(boxstyle="round,pad=0.3", facecolor="white", edgecolor="black", linewidth=0.9),
)
ax.annotate("", xy=(12_000, sec[i]["p50_ms"]), xytext=(12_000, idx[i]["p50_ms"]),
            arrowprops=dict(arrowstyle="<->", color="black", linewidth=1.0))

fig.tight_layout()
for formato in ("png", "svg"):
    fig.savefig(DESTINO / f"fig5_latencia.{formato}", dpi=180, facecolor="white")
print("escrito", DESTINO / "fig5_latencia.png")
