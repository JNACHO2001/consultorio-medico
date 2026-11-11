"""Calcula en qué página cae cada título del índice a partir del PDF del informe.

Uso: python3 paginas.py            -> convierte el .docx a PDF y escribe paginas.json
     python3 paginas.py --verificar -> falla si paginas.json no coincide con el PDF (índice desactualizado)
"""
import json
import re
import subprocess
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
DOCX = AQUI.parent / "Informe_Unidad2_Arquitectura_Distribuida.docx"
PDF = DOCX.with_suffix(".pdf")
SOFFICE = "/mnt/skills/public/docx/scripts/office/soffice.py"

subprocess.run(["python3", SOFFICE, "--headless", "--convert-to", "pdf", "--outdir", str(AQUI.parent), str(DOCX)],
               check=True, capture_output=True)
total = int(re.search(r"Pages:\s+(\d+)", subprocess.run(["pdfinfo", str(PDF)], capture_output=True, text=True).stdout).group(1))
paginas_texto = [
    subprocess.run(["pdftotext", "-f", str(n), "-l", str(n), "-layout", str(PDF), "-"], capture_output=True, text=True).stdout
    for n in range(1, total + 1)
]
titulos = json.loads((AQUI / "titulos.json").read_text(encoding="utf-8"))
resultado, limite = {}, total
for tit in reversed(titulos):  # el contenido va después del índice: se busca de atrás hacia adelante
    clave = tit["texto"][:40]
    for n in range(limite, 1, -1):
        lineas = [l.strip() for l in paginas_texto[n - 1].splitlines()]
        # las líneas del índice terminan en puntos guía o varios espacios y el número; los títulos reales, no
        if any(l.startswith(clave) and not re.search(r"(\.{2,}|\s{2,})\d+$", l) for l in lineas):
            resultado[tit["texto"]] = n
            limite = n
            break
    else:
        sys.exit(f"No se encontró el título en el PDF: {tit['texto']}")
resultado = {t_["texto"]: resultado[t_["texto"]] for t_ in titulos}

ruta = AQUI / "paginas.json"
if "--verificar" in sys.argv:
    previo = json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else {}
    if previo != resultado:
        sys.exit("El índice está desactualizado: vuelva a ejecutar generar.sh")
    print(f"Índice verificado ({total} páginas).")
else:
    ruta.write_text(json.dumps(resultado, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{total} páginas; {len(resultado)} títulos ubicados.")
