"""Diagramas UML de la navegación del sistema (Unidad 3), en blanco y negro.

  08 Componentes: la navegación del frontend y el servicio de catálogo del backend.
  09 Clases: tabla de rutas, despachador y estrategias de búsqueda.
  10 Secuencia: búsqueda incremental de un diagnóstico, con retardo y cancelación.
  11 Actividad: flujo de navegación desde que el usuario pide una pantalla.

Requisitos: Graphviz (``dot``) y Matplotlib.

    python docs/uml/render_navegacion.py

Salida: ``docs/uml/img/{08,09,10,11}_*.png`` y ``.svg`` (más las fuentes ``.dot``).
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, Rectangle  # noqa: E402

AQUI = Path(__file__).resolve().parent
IMG = AQUI / "img"
IMG.mkdir(exist_ok=True)

FUENTE = "DejaVu Sans"
BLANCO, NEGRO, GRIS, GRIS_C = "white", "#000000", "#888888", "#E8E8E8"


def dot_a_imagen(nombre: str, contenido: str) -> None:
    fuente = AQUI / f"{nombre}.dot"
    fuente.write_text(contenido, encoding="utf-8")
    for formato, extra in (("png", ["-Gdpi=170"]), ("svg", [])):
        subprocess.run(["dot", f"-T{formato}", *extra, str(fuente), "-o", str(IMG / f"{nombre}.{formato}")], check=True)
    print("escrito", IMG / f"{nombre}.png")


# ------------------------------------------------------------------ 08 componentes
COMPONENTES = f"""digraph componentes {{
  graph [rankdir=TB, fontname="{FUENTE}", fontsize=15, labelloc=t, pad=0.35, nodesep=0.35, ranksep=0.65,
         compound=true, bgcolor="white",
         label="Diagrama de componentes — Navegación del sistema «Salud Integral»\\n "];
  node  [fontname="{FUENTE}", fontsize=10.5, shape=component, style="filled", fillcolor="white",
         color="black", penwidth=1.3, margin="0.16,0.11"];
  edge  [fontname="{FUENTE}", fontsize=9.5, color="black", arrowsize=0.75];

  subgraph cluster_nav {{
    label="Navegador · aplicación de una sola página (frontend)"; style="rounded"; color="black";
    fontsize=12; penwidth=1.6;
    HASH  [label="Barra de direcciones\\n#/ruta/parámetro", shape=box, style="rounded,filled", fillcolor="{GRIS_C}"];
    DESP  [label="Despachador  mostrar()\\n«Front Controller»\\nvalida rol · marca activo ·\\ndescarta montajes viejos"];
    TABLA [label="Tabla de rutas  RUTAS\\n17 rutas: título, roles,\\npadre, montar()", shape=folder, style="filled", fillcolor="{GRIS_C}"];
    MENU  [label="Menú lateral\\nsolo las rutas del rol"];
    VISTA [label="Vista montada\\nmontarAgenda, montarIngresos, …\\n«Strategy»"];
    CLIEN [label="Cliente HTTP  api.js\\nsesión · errores · reintento", fillcolor="{GRIS_C}"];
  }}

  subgraph cluster_api {{
    label="Servidor de aplicación (FastAPI)"; style="rounded"; color="black"; fontsize=12; penwidth=1.6;
    REST  [label="API REST\\n/api/cie10 · /api/pacientes …"];
    GUARD [label="requiere_roles()\\nsegunda validación del rol", shape=box, style="rounded,filled", fillcolor="{GRIS_C}"];
    SVC   [label="Cie10Service\\nbuscar() · descripcion()"];
    IEST  [label="«interface»\\nEstrategiaBusqueda", shape=box, style="rounded,dashed,filled", fillcolor="white"];
    SEC   [label="BusquedaSecuencial\\nrecorre el catálogo"];
    IDX   [label="BusquedaIndiceInvertido\\níndice de prefijos"];
  }}

  CAT [label="Catálogo CIE-10\\n(muestra de 149 códigos;\\noficial: más de 12.000)", shape=cylinder, style=filled, fillcolor="{GRIS_C}"];

  HASH  -> DESP  [label="hashchange"];
  DESP  -> TABLA [label="consulta"];
  DESP  -> MENU  [label="marca activo"];
  MENU  -> HASH  [label="href #/ruta", style=dashed];
  DESP  -> VISTA [label="montar(contenedor)"];
  VISTA -> CLIEN [label="get/post"];
  CLIEN -> REST  [label="HTTPS + token"];
  REST  -> GUARD;
  GUARD -> SVC   [label="autorizado"];
  SVC   -> IEST  [label="delega", style=dashed];
  IEST  -> SEC   [arrowhead=empty, style=dashed, dir=back];
  IEST  -> IDX   [arrowhead=empty, style=dashed, dir=back];
  SEC   -> CAT;
  IDX   -> CAT   [label="indexa al arrancar"];
}}
"""

# ------------------------------------------------------------------ 09 clases
CLASES = f"""digraph clases {{
  graph [rankdir=TB, fontname="{FUENTE}", fontsize=15, labelloc=t, pad=0.35, nodesep=0.45, ranksep=0.6,
         bgcolor="white", label="Diagrama de clases — Rutas y estrategias de búsqueda\\n "];
  node  [fontname="{FUENTE}", fontsize=10, shape=record, style=filled, fillcolor="white", color="black", penwidth=1.2];
  edge  [fontname="{FUENTE}", fontsize=9.5, color="black", arrowsize=0.8];

  Ruta  [label="{{Ruta|+ titulo: str\\l+ roles: Rol[]\\l+ oculta: bool\\l+ padre: Ruta?\\l|+ montar(contenedor, ctx)\\l}}"];
  Tabla [label="{{TablaDeRutas|- rutas: Map\\<str, Ruta\\>\\l- inicio: Map\\<Rol, str\\>\\l|+ resolver(hash): Ruta\\l+ visibles(rol): Ruta[]\\l+ ruta_padre(r): Ruta?\\l}}"];
  Desp  [label="{{Despachador  «Front Controller»|- version: int\\l|+ mostrar(): void\\l- autorizar(ruta, usuario)\\l- marcar_activo(ruta)\\l}}"];

  Svc   [label="{{Cie10Service|- estrategia: EstrategiaBusqueda\\l|+ buscar(q, limite): (str, str)[]\\l+ descripcion(codigo): str?\\l}}"];
  IEst  [label="{{«interface»\\nEstrategiaBusqueda|+ nombre: str\\l|+ buscar(q): Iterator\\l+ descripcion(codigo): str?\\l}}", style="filled,dashed"];
  Sec   [label="{{BusquedaSecuencial|- indice: (str, str, str)[]\\l|+ buscar(q): Iterator\\l  O(n · t) por consulta\\l}}"];
  Idx   [label="{{BusquedaIndiceInvertido|- postings: Map\\<str, Set\\<int\\>\\>\\l- entradas: (str, str)[]\\l|+ buscar(q): Iterator\\l  interseca listas cortas\\l+ tamano_indice: int\\l}}"];

  Desp  -> Tabla [label="consulta", arrowhead=vee];
  Tabla -> Ruta  [label="1..*", arrowhead=none, taillabel="◆", fontsize=9];
  Ruta  -> Ruta  [label="padre  0..1", arrowhead=vee, style=dashed, constraint=false];
  Desp  -> Ruta  [label="montar()", arrowhead=vee, style=dashed];
  Svc   -> IEst  [label="usa", arrowhead=vee];
  IEst  -> Sec   [arrowhead=empty, dir=back, style=dashed];
  IEst  -> Idx   [arrowhead=empty, dir=back, style=dashed];
  {{rank=same; Sec; Idx;}}
}}
"""

# ------------------------------------------------------------------ 11 actividad
ACTIVIDAD = f"""digraph actividad {{
  graph [rankdir=TB, fontname="{FUENTE}", fontsize=15, labelloc=t, pad=0.35, nodesep=0.3, ranksep=0.42,
         bgcolor="white", label="Diagrama de actividad — Resolución de una ruta\\n "];
  node  [fontname="{FUENTE}", fontsize=10, shape=box, style="rounded,filled", fillcolor="white",
         color="black", penwidth=1.2, margin="0.16,0.09"];
  edge  [fontname="{FUENTE}", fontsize=9.5, color="black", arrowsize=0.75];

  ini  [label="", shape=circle, style=filled, fillcolor="black", width=0.22, height=0.22];
  fin  [label="", shape=doublecircle, style=filled, fillcolor="black", width=0.20, height=0.20];

  cambio [label="Cambia la dirección  #/ruta/parámetro"];
  leer   [label="Leer la ruta y sus parámetros"];
  existe [label="¿La ruta existe?", shape=diamond, style=filled, height=0.75, width=1.9];
  permiso[label="¿El rol tiene permiso?", shape=diamond, style=filled, height=0.75, width=2.1];
  inicio [label="Redirigir a la pantalla de inicio del rol"];
  marcar [label="Marcar la opción activa del menú\\n(la de la ruta padre, si es anidada)"];
  token  [label="Tomar el turno:  version = ++version"];
  cargar [label="Mostrar «Cargando…» y montar la vista"];
  pedir  [label="Pedir los datos a la API\\n(el servidor revalida el rol)"];
  vigente[label="¿Sigue siendo\\nel turno vigente?", shape=diamond, style=filled, height=0.8, width=2.1];
  pintar [label="Pintar el contenido y llevar el foco"];
  descart[label="Descartar la respuesta\\n(el usuario ya navegó a otra parte)", style="rounded,filled,dashed", fillcolor="{GRIS_C}"];
  error  [label="Mostrar el aviso de error\\nsin perder la navegación", style="rounded,filled,dashed", fillcolor="{GRIS_C}"];

  ini -> cambio -> leer -> existe;
  existe  -> inicio  [label="  no"];
  existe  -> permiso [label="  sí"];
  permiso -> inicio  [label="  no"];
  permiso -> marcar  [label="  sí"];
  inicio  -> leer    [style=dashed];
  marcar -> token -> cargar -> pedir -> vigente;
  vigente -> pintar  [label="  sí"];
  vigente -> descart [label="  no"];
  pedir   -> error   [label="  falla", style=dashed];
  pintar -> fin;
  descart -> fin;
  error -> fin;
}}
"""


# ------------------------------------------------------------------ 10 secuencia
def secuencia() -> None:
    """Búsqueda incremental de un diagnóstico: retardo, índice y cancelación."""
    fig, ax = plt.subplots(figsize=(12.6, 8.6))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")
    ax.set_title(
        "Diagrama de secuencia — Búsqueda incremental de un diagnóstico (CIE-10)",
        fontsize=14, fontfamily=FUENTE, pad=12,
    )

    actores = [
        ("Médico", 7), ("Buscador\n(vista)", 25), ("api.js", 42),
        ("API REST\n/api/cie10", 59), ("Cie10Service", 76), ("Estrategia\n(índice invertido)", 93),
    ]
    cabeza_y, pie_y = 95, 4
    for nombre, x in actores:
        ax.add_patch(Rectangle((x - 7.2, cabeza_y - 5), 14.4, 7.0, facecolor=BLANCO, edgecolor=NEGRO, linewidth=1.3))
        ax.text(x, cabeza_y - 1.5, nombre, ha="center", va="center", fontsize=9.5, fontfamily=FUENTE)
        ax.plot([x, x], [cabeza_y - 5, pie_y], color=GRIS, linewidth=0.9, linestyle=(0, (4, 3)))

    def mensaje(x1, x2, y, texto, cursiva=False, retorno=False, dy=1.4):
        ax.add_patch(FancyArrowPatch(
            (x1, y), (x2, y), arrowstyle="-|>", mutation_scale=11, linewidth=1.15, color=NEGRO,
            linestyle="--" if retorno else "-",
        ))
        ax.text((x1 + x2) / 2, y + dy, texto, ha="center", va="bottom", fontsize=8.5,
                fontfamily=FUENTE, style="italic" if cursiva else "normal")

    def activacion(x, y1, y2):
        ax.add_patch(Rectangle((x - 1.0, y2), 2.0, y1 - y2, facecolor=BLANCO, edgecolor=NEGRO, linewidth=1.0))

    def nota(x, y, texto, ancho=26, alto=6.4):
        ax.add_patch(Rectangle((x, y), ancho, alto, facecolor=GRIS_C, edgecolor=NEGRO, linewidth=0.9))
        ax.text(x + ancho / 2, y + alto / 2, texto, ha="center", va="center", fontsize=8.1, fontfamily=FUENTE)

    def marco(y_inf, y_sup, etiqueta, condicion, ancho_etq=13.5):
        ax.add_patch(Rectangle((2, y_inf), 96, y_sup - y_inf, facecolor="none", edgecolor=NEGRO, linewidth=1.1))
        ax.add_patch(Rectangle((2, y_sup - 4.4), ancho_etq, 4.4, facecolor=BLANCO, edgecolor=NEGRO, linewidth=1.1))
        ax.text(2 + ancho_etq / 2, y_sup - 2.2, etiqueta, ha="center", va="center", fontsize=9,
                fontweight="bold", fontfamily=FUENTE)
        ax.text(2 + ancho_etq + 2, y_sup - 2.2, condicion, ha="left", va="center", fontsize=8.5,
                fontfamily=FUENTE, style="italic")

    x = {n: v for n, v in actores}
    med, vis, cli, api, svc, est = (x["Médico"], x["Buscador\n(vista)"], x["api.js"],
                                    x["API REST\n/api/cie10"], x["Cie10Service"], x["Estrategia\n(índice invertido)"])

    # 1) el usuario escribe letra a letra: cada pulsación reinicia el retardo
    marco(63, 88, "loop", "[por cada pulsación:  d · i · a · b]")
    mensaje(med, vis - 1.0, 81.5, "escribe una letra")
    activacion(vis, 82.5, 68)
    ax.add_patch(FancyArrowPatch((vis + 1.0, 77.5), (vis + 7, 77.5), arrowstyle="-", linewidth=1.1, color=NEGRO))
    ax.add_patch(FancyArrowPatch((vis + 7, 77.5), (vis + 7, 73.5), arrowstyle="-", linewidth=1.1, color=NEGRO))
    ax.add_patch(FancyArrowPatch((vis + 7, 73.5), (vis + 1.0, 73.5), arrowstyle="-|>", mutation_scale=11,
                                 linewidth=1.1, color=NEGRO))
    ax.text(vis + 8.5, 75.5, "reiniciar el retardo (250 ms)", ha="left", va="center", fontsize=8.4,
            fontfamily=FUENTE, style="italic")
    nota(2.5, 64.5, "Solo la última pulsación\nllega a la red:\n4 peticiones → 1", ancho=19, alto=7.0)

    # 2) una sola petición, ya vencido el retardo
    mensaje(vis, cli - 1.0, 58, "buscar(«diab»)  — vencido el retardo")
    activacion(cli, 59, 23)
    mensaje(cli, api - 1.0, 53, "GET /api/cie10?q=diab  (+ token de sesión)")
    activacion(api, 54, 27)
    ax.add_patch(FancyArrowPatch((api + 1.0, 48.5), (api + 6, 48.5), arrowstyle="-", linewidth=1.1, color=NEGRO))
    ax.add_patch(FancyArrowPatch((api + 6, 48.5), (api + 6, 45.5), arrowstyle="-", linewidth=1.1, color=NEGRO))
    ax.add_patch(FancyArrowPatch((api + 6, 45.5), (api + 1.0, 45.5), arrowstyle="-|>", mutation_scale=11,
                                 linewidth=1.1, color=NEGRO))
    ax.text(api + 7.4, 47, "requiere_roles(MÉDICO, ADMIN)", ha="left", va="center", fontsize=8.4,
            fontfamily=FUENTE, style="italic")
    mensaje(api, svc - 1.0, 41, "buscar(«diab», limite = 20)")
    activacion(svc, 42, 31)
    mensaje(svc, est - 1.0, 37, "buscar(«diab»)")
    activacion(est, 38, 33.5)

    # 3) retornos
    mensaje(est - 1.0, svc + 1.0, 34.5, "iterador de coincidencias", retorno=True, cursiva=True, dy=1.2)
    mensaje(svc - 1.0, api + 1.0, 29.5, "20 diagnósticos ordenados", retorno=True, cursiva=True, dy=1.2)
    mensaje(api - 1.0, cli + 1.0, 25.5, "200 OK · [{codigo, descripcion}]", retorno=True, cursiva=True, dy=1.2)
    mensaje(cli - 1.0, vis + 1.0, 21.5, "respuesta", retorno=True, cursiva=True, dy=1.2)
    nota(66.5, 20.0, "El índice interseca las listas\ncortas y devuelve un iterador\nperezoso: solo se construyen\nlos 20 resultados de la página", ancho=31, alto=8.4)

    # 4) la respuesta se usa solo si sigue siendo la vigente
    marco(4.5, 18.5, "alt", "[la consulta sigue vigente]   /   [el usuario ya escribió otra cosa]", ancho_etq=11)
    ax.text(33, 11.8, "pintar la lista y permitir elegir el código", ha="center", va="center",
            fontsize=8.6, fontfamily=FUENTE)
    ax.plot([2, 65], [9.6, 9.6], color=NEGRO, linewidth=0.9, linestyle=(0, (5, 4)))
    ax.text(33, 7.0, "descartar la respuesta: la pantalla ya no la necesita", ha="center", va="center",
            fontsize=8.6, fontfamily=FUENTE)

    fig.tight_layout()
    for formato in ("png", "svg"):
        fig.savefig(IMG / f"10_secuencia_navegacion.{formato}", dpi=170, facecolor="white")
    plt.close(fig)
    print("escrito", IMG / "10_secuencia_navegacion.png")


def main() -> None:
    dot_a_imagen("08_componentes_navegacion", COMPONENTES)
    dot_a_imagen("09_clases_navegacion", CLASES)
    secuencia()
    dot_a_imagen("11_actividad_navegacion", ACTIVIDAD)


if __name__ == "__main__":
    main()
