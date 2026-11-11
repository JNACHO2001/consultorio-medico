#!/usr/bin/env bash
# Regenera el informe: dos pasadas (la segunda ya con los números de página reales) y verificación.
set -euo pipefail
cd "$(dirname "$0")"
rm -f paginas.json
node generar_informe.js
python3 paginas.py
node generar_informe.js
python3 paginas.py --verificar
