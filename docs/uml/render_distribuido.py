"""Genera los diagramas UML a color de la arquitectura distribuida (Unidad 2).

* 05 Componentes y 07 Despliegue: se escriben como DOT (``*.dot``) y se dibujan con Graphviz.
* 06 Secuencia: se dibuja con Matplotlib (lifelines, mensajes y el marco ``alt``).

Requisitos: Graphviz (comando ``dot``) y Matplotlib.

    python docs/uml/render_distribuido.py

Salida: ``docs/uml/img/0{5,6,7}_*.png`` y ``.svg``, más las fuentes ``05_*.dot`` y ``07_*.dot``.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch, Rectangle  # noqa: E402

AQUI = Path(__file__).resolve().parent
IMG = AQUI / "img"
IMG.mkdir(exist_ok=True)

FUENTE = "DejaVu Sans"

# Paleta (una por capa/rol; se repite en los tres diagramas)
AZUL, AZUL_L = "#1F5FA8", "#DCE9F8"       # API / servicio
VERDE, VERDE_L = "#2E7D32", "#DDF0DD"     # patrones (proxy, mediador)
NARANJA, NARANJA_L = "#C45A00", "#FFE9D2"  # nodos
MORADO, MORADO_L = "#6A3FA0", "#EBE0F7"   # observadores
GRIS, GRIS_L = "#555555", "#EEEEEE"       # externo
ROJO = "#B3261E"


def dot_a_imagen(nombre: str, contenido: str) -> None:
    fuente = AQUI / f"{nombre}.dot"
    fuente.write_text(contenido, encoding="utf-8")
    for formato, extra in (("png", ["-Gdpi=170"]), ("svg", [])):
        subprocess.run(["dot", f"-T{formato}", *extra, str(fuente), "-o", str(IMG / f"{nombre}.{formato}")], check=True)


# ---------------------------------------------------------------------- 05 componentes

COMPONENTES = f"""digraph componentes {{
  graph [rankdir=TB, fontname="{FUENTE}", fontsize=15, labelloc=t, pad=0.35, nodesep=0.4, ranksep=0.8, compound=true,
         label="Diagrama de componentes — Facturación electrónica distribuida\\nSistema «Salud Integral»\\n "];
  node  [fontname="{FUENTE}", fontsize=11, shape=component, style="filled", penwidth=1.4, margin="0.18,0.12"];
  edge  [fontname="{FUENTE}", fontsize=10, color="#444444", arrowsize=0.8];

  subgraph cluster_api {{
    label="Servidor de aplicación (proceso uvicorn · FastAPI)"; style="rounded,filled"; fillcolor="#F4F8FD"; color="{AZUL}";
    fontcolor="{AZUL}"; fontsize=12; penwidth=2;
    API   [label="API REST\\n/api/electronica/...", fillcolor="{AZUL_L}", color="{AZUL}"];
    SVC   [label="FacturacionElectronicaService\\n1) reservar (con candado)\\n2) transmitir (sin candado)", fillcolor="{AZUL_L}", color="{AZUL}"];
    IPROV [label="«interface»\\nIProveedorTecnologico", shape=box, style="rounded,filled,dashed", fillcolor="white", color="{AZUL}"];
    PROXY [label="ProveedorProxy  «Proxy»\\nreintentos · espera exponencial\\nclave de idempotencia", fillcolor="{VERDE_L}", color="{VERDE}"];
    MED   [label="MediadorNodos  «Mediator»\\nbalanceo (menos carga) ·\\ncircuit breaker por nodo", fillcolor="{VERDE_L}", color="{VERDE}"];
    CLI   [label="ClienteNodo\\npool de conexiones TCP", fillcolor="{VERDE_L}", color="{VERDE}"];
    BUS   [label="BusEventos  «Observer»\\n(hilo despachador propio)", fillcolor="{MORADO_L}", color="{MORADO}"];
    MET   [label="Metricas\\n(observador: p50/p95/p99)", fillcolor="{MORADO_L}", color="{MORADO}"];
    VIG   [label="Vigilante\\n(hilo de latidos)", fillcolor="{MORADO_L}", color="{MORADO}"];
  }}

  subgraph cluster_nodos {{
    label="Nodos proveedor (N procesos independientes)"; style="rounded,filled"; fillcolor="#FFF8EE"; color="{NARANJA}";
    fontcolor="{NARANJA}"; fontsize=12; penwidth=2;
    subgraph cluster_n1 {{
      label="nodo-1  (puerto 9101)"; style="rounded,filled"; fillcolor="white"; color="{NARANJA}"; fontcolor="{NARANJA}";
      SRV   [label="Servidor TCP\\n(un hilo por conexión)", fillcolor="{NARANJA_L}", color="{NARANJA}"];
      POOL  [label="Pool de hilos\\n(hilos + cola acotada)", fillcolor="{NARANJA_L}", color="{NARANJA}"];
      CACHE [label="Caché de idempotencia", fillcolor="{NARANJA_L}", color="{NARANJA}"];
      PROV  [label="ProveedorSimulado\\n(validación local)", fillcolor="{NARANJA_L}", color="{NARANJA}"];
    }}
    NN [label="nodo-2 … nodo-N\\n(misma estructura)", fillcolor="{NARANJA_L}", color="{NARANJA}"];
  }}

  DIAN [label="Proveedor tecnológico\\nautorizado DIAN\\n(trabajo futuro)", style="filled,dashed", fillcolor="{GRIS_L}", color="{GRIS}", fontcolor="{GRIS}"];

  API -> SVC;
  SVC -> IPROV [label=" usa"];
  PROXY -> IPROV [arrowhead=onormal, style=dashed, label=" implementa"];
  PROXY -> MED [label=" despachar()"];
  MED -> CLI [label=" solicitar()"];
  CLI -> SRV [label=" TCP · JSON por línea", color="{NARANJA}", penwidth=1.8];
  CLI -> NN  [label=" TCP", color="{NARANJA}", penwidth=1.8];
  SRV -> POOL;
  POOL -> CACHE;
  POOL -> PROV;
  PROXY -> BUS [label=" publica", color="{MORADO}"];
  MED -> BUS [label=" publica", color="{MORADO}"];
  BUS -> MET [label=" notifica", color="{MORADO}"];
  VIG -> MED [label=" sondear()", color="{MORADO}"];
  PROV -> DIAN [style=dashed, color="{GRIS}", label=" (futuro)"];
}}
"""

# ---------------------------------------------------------------------- 07 despliegue

DESPLIEGUE = f"""digraph despliegue {{
  graph [rankdir=TB, fontname="{FUENTE}", fontsize=15, labelloc=t, pad=0.35, nodesep=0.5, ranksep=0.9, compound=true,
         label="Diagrama de despliegue — Facturación electrónica distribuida\\nSistema «Salud Integral»\\n "];
  node  [fontname="{FUENTE}", fontsize=11, style="filled", penwidth=1.4, margin="0.2,0.12"];
  edge  [fontname="{FUENTE}", fontsize=10, color="#444444", arrowsize=0.8];

  subgraph cluster_cli {{
    label="Equipo del usuario  «dispositivo»"; style="rounded,filled"; fillcolor="#F6F6F6"; color="{GRIS}"; fontcolor="{GRIS}"; penwidth=2;
    NAV [label="Navegador web\\n(recepción, médico, administración)", shape=box, fillcolor="white", color="{GRIS}"];
  }}

  subgraph cluster_app {{
    label="Servidor de aplicación  «contenedor Docker · Render / Cloud Run»"; style="rounded,filled"; fillcolor="#F4F8FD";
    color="{AZUL}"; fontcolor="{AZUL}"; penwidth=2;
    API [label="API REST FastAPI + interfaz web\\n«artefacto»", shape=component, fillcolor="{AZUL_L}", color="{AZUL}"];
    SVCS [label="Servicios y repositorios en memoria\\n«artefacto»", shape=component, fillcolor="{AZUL_L}", color="{AZUL}"];
    PROX [label="ProveedorProxy + MediadorNodos\\n«artefacto»", shape=component, fillcolor="{VERDE_L}", color="{VERDE}"];
    HILOS [label="Hilos del proceso:\\n· servidor uvicorn\\n· bus-eventos (Observer)\\n· vigilante-nodos (latidos)", shape=note, fillcolor="{MORADO_L}", color="{MORADO}"];
  }}

  subgraph cluster_h1 {{
    label="Host de nodos 1  «máquina o contenedor»"; style="rounded,filled"; fillcolor="#FFF8EE"; color="{NARANJA}"; fontcolor="{NARANJA}"; penwidth=2;
    N1 [label="nodo-1  :9101\\n«proceso Python»\\nservidor TCP + pool de 4 hilos\\n+ caché de idempotencia", shape=box3d, fillcolor="{NARANJA_L}", color="{NARANJA}"];
    N2 [label="nodo-2  :9102\\n«proceso Python»\\nservidor TCP + pool de 4 hilos\\n+ caché de idempotencia", shape=box3d, fillcolor="{NARANJA_L}", color="{NARANJA}"];
  }}
  subgraph cluster_h2 {{
    label="Host de nodos 2  «máquina o contenedor»"; style="rounded,filled"; fillcolor="#FFF8EE"; color="{NARANJA}"; fontcolor="{NARANJA}"; penwidth=2;
    N3 [label="nodo-3  :9101\\n«proceso Python»\\nservidor TCP + pool de 4 hilos\\n+ caché de idempotencia", shape=box3d, fillcolor="{NARANJA_L}", color="{NARANJA}"];
  }}

  DIAN [label="Proveedor tecnológico autorizado\\n«sistema externo · trabajo futuro»", shape=box3d, style="filled,dashed", fillcolor="{GRIS_L}", color="{GRIS}", fontcolor="{GRIS}"];

  NAV -> API [label=" HTTPS :443\\n JSON", penwidth=1.6, color="{AZUL}"];
  API -> SVCS;
  SVCS -> PROX;
  PROX -> HILOS [style=dotted, arrowhead=none];
  PROX -> N1 [label=" TCP :9101\\n JSON por línea", penwidth=1.8, color="{NARANJA}"];
  PROX -> N2 [label=" TCP :9102", penwidth=1.8, color="{NARANJA}"];
  PROX -> N3 [label=" TCP :9101", penwidth=1.8, color="{NARANJA}"];
  N1 -> DIAN [style=dashed, color="{GRIS}", label=" HTTPS\\n (futuro)"];
  N2 -> DIAN [style=dashed, color="{GRIS}"];
  N3 -> DIAN [style=dashed, color="{GRIS}"];
}}
"""

# ---------------------------------------------------------------------- 06 secuencia

PARTICIPANTES = [
    ("Recepción\n(navegador)", GRIS, GRIS_L),
    ("Servicio de\nfacturación\nelectrónica", AZUL, AZUL_L),
    ("ProveedorProxy", VERDE, VERDE_L),
    ("MediadorNodos", VERDE, VERDE_L),
    ("Nodo A\n(hilo de conexión\n+ pool de hilos)", NARANJA, NARANJA_L),
    ("Nodo B\n(hilo de conexión\n+ pool de hilos)", NARANJA, NARANJA_L),
    ("BusEventos\n+ Métricas", MORADO, MORADO_L),
]


def secuencia() -> None:
    n = len(PARTICIPANTES)
    ancho_col = 2.35
    xs = [i * ancho_col for i in range(n)]
    # (clase, origen, destino, texto, y) — y se asigna al recorrer
    pasos = [
        ("msg", 0, 1, "POST /emitir"),
        ("self", 1, 1, "reservar(): candado → consecutivo, CUFE y XML;\nguarda estado GENERADO"),
        ("msg", 1, 2, "enviar(documento)   «fuera del candado»"),
        ("msg", 2, 3, "despachar(mensaje, excluidos = ∅)"),
        ("msg", 3, 4, "ENVIAR (clave de idempotencia)"),
        ("alt_ini", "Nodo A atiende", None, None),
        ("self", 4, 4, "hilo de conexión → pool de hilos:\nvalida y «transmite» (≈ 40 ms)"),
        ("ret", 4, 3, "respuesta {aceptado, código}"),
        ("alt_sep", "Nodo A caído, saturado o lento  (conexión · timeout · OCUPADO)", None, None),
        ("ret", 4, 3, "✗ conexión rechazada / sin respuesta"),
        ("self", 3, 3, "registra fallo; circuit breaker\n(abre tras N fallos seguidos)"),
        ("msg", 3, 6, "publica intento.fallido  (asíncrono)"),
        ("ret", 3, 2, "ErrorDespacho(Nodo A)"),
        ("self", 2, 2, "espera con backoff + jitter"),
        ("msg", 2, 3, "despachar(mensaje, excluidos = {A})"),
        ("msg", 3, 5, "ENVIAR (misma clave de idempotencia)"),
        ("self", 5, 5, "hilo de conexión → pool de hilos:\nvalida y «transmite»"),
        ("ret", 5, 3, "respuesta {aceptado, código}"),
        ("alt_fin", None, None, None),
        ("ret", 3, 2, "(nodo, respuesta)"),
        ("msg", 2, 6, "publica envio.exitoso  (asíncrono)"),
        ("ret", 2, 1, "RespuestaProveedor"),
        ("self", 1, 1, "transmitir(): guarda ACEPTADO\ny registra auditoría"),
        ("ret", 1, 0, "201 documento electrónico ACEPTADO"),
    ]
    paso_y = 0.62
    alto_total = 2.6 + sum(2.0 if p[0] == "self" else (0.55 if p[0] in ("alt_ini", "alt_sep", "alt_fin") else 1.0) for p in pasos) * paso_y
    fig, ax = plt.subplots(figsize=(n * ancho_col * 1.02, alto_total * 0.62))
    ax.set_xlim(-1.4, xs[-1] + 1.4)
    ax.set_ylim(-alto_total, 1.2)
    ax.axis("off")

    # Cabeceras
    for x, (nombre, color, claro) in zip(xs, PARTICIPANTES):
        ax.add_patch(FancyBboxPatch((x - 1.0, 0.0), 2.0, 1.0, boxstyle="round,pad=0.02,rounding_size=0.12",
                                    fc=claro, ec=color, lw=2))
        ax.text(x, 0.5, nombre, ha="center", va="center", fontsize=9, fontweight="bold", color=color, family=FUENTE)

    y = -0.45
    marcas: list[tuple[float, float]] = []  # para dibujar las líneas de vida al final
    alt_inicio = alt_sep_y = None
    for paso in pasos:
        tipo = paso[0]
        if tipo in ("msg", "ret"):
            _, a, b, texto = paso
            y -= paso_y * 1.0
            estilo = "--" if tipo == "ret" else "-"
            color = ROJO if texto.startswith("✗") else "#222222"
            ax.annotate("", xy=(xs[b], y), xytext=(xs[a], y),
                        arrowprops=dict(arrowstyle="-|>", lw=1.5, color=color, linestyle=estilo, shrinkA=0, shrinkB=0))
            ax.text((xs[a] + xs[b]) / 2, y + 0.09, texto, ha="center", va="bottom", fontsize=8.2, color=color, family=FUENTE,
                    bbox=dict(fc="white", ec="none", pad=0.6, alpha=0.9))
        elif tipo == "self":
            _, a, _, texto = paso
            y -= paso_y * 1.45
            x = xs[a]
            ax.plot([x, x + 0.55, x + 0.55, x], [y + 0.22, y + 0.22, y - 0.22, y - 0.22], color="#222222", lw=1.3)
            ax.annotate("", xy=(x, y - 0.22), xytext=(x + 0.12, y - 0.22),
                        arrowprops=dict(arrowstyle="-|>", lw=1.3, color="#222222", shrinkA=0, shrinkB=0))
            ax.text(x + 0.68, y, texto, ha="left", va="center", fontsize=8, color="#222222", family=FUENTE,
                    bbox=dict(fc="#FFFBE6", ec="#D4C77A", pad=2.0, boxstyle="round,pad=0.25"))
            y -= paso_y * 0.4
        elif tipo == "alt_ini":
            y -= paso_y * 0.55
            alt_inicio = y + 0.12
            alt_etiqueta = paso[1]
            ax.text(xs[2] - 0.45, alt_inicio - 0.16, f"[{alt_etiqueta}]", ha="left", va="center", fontsize=8.2, style="italic",
                    color="#333333", family=FUENTE, bbox=dict(fc="white", ec="none", pad=0.5))
        elif tipo == "alt_sep":
            y -= paso_y * 0.55
            alt_sep_y = y + 0.30
            ax.plot([xs[2] - 1.2, xs[6] + 1.1], [alt_sep_y, alt_sep_y], color="#777777", lw=1.1, linestyle=(0, (5, 3)))
            ax.text(xs[2] - 1.1, y - 0.02, f"[{paso[1]}]", ha="left", va="center", fontsize=8.2, style="italic",
                    color="#333333", family=FUENTE, bbox=dict(fc="white", ec="none", pad=0.5))
        elif tipo == "alt_fin":
            y -= paso_y * 0.55
            fin = y + 0.35
            ax.add_patch(Rectangle((xs[2] - 1.2, fin), xs[6] + 1.1 - (xs[2] - 1.2), alt_inicio - fin, fc="none", ec="#777777", lw=1.4))
            ax.add_patch(Rectangle((xs[2] - 1.2, alt_inicio - 0.32), 0.62, 0.32, fc="#E7E7E7", ec="#777777", lw=1.2))
            ax.text(xs[2] - 0.89, alt_inicio - 0.16, "alt", ha="center", va="center", fontsize=8.5, fontweight="bold", family=FUENTE)
        marcas.append((y, y))

    fondo = y - 0.7
    for x, (_, color, _c) in zip(xs, PARTICIPANTES):
        ax.plot([x, x], [0.0, fondo], color=color, lw=1.2, linestyle=(0, (4, 4)), zorder=0)
        ax.add_patch(Rectangle((x - 0.07, fondo), 0.14, 0.0, fc=color, ec=color))
    ax.set_ylim(fondo - 0.4, 1.3)
    ax.text(xs[-1] / 2, 1.28, "Diagrama de secuencia — Emitir una factura electrónica con failover entre nodos",
            ha="center", va="bottom", fontsize=12.5, fontweight="bold", family=FUENTE)
    fig.savefig(IMG / "06_secuencia_distribuida.png", dpi=170, bbox_inches="tight", facecolor="white")
    fig.savefig(IMG / "06_secuencia_distribuida.svg", bbox_inches="tight", facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    dot_a_imagen("05_componentes_distribuido", COMPONENTES)
    secuencia()
    dot_a_imagen("07_despliegue_distribuido", DESPLIEGUE)
    print("Diagramas generados en", IMG)
