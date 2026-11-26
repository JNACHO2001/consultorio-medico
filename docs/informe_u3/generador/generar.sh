#!/usr/bin/env bash
# Regenera el informe de la Unidad 3: dos pasadas (la segunda ya con los números de página) y verificación.
set -euo pipefail
cd "$(dirname "$0")"
rm -f paginas.json
node generar_informe.js
python3 paginas.py
node generar_informe.js
python3 paginas.py --verificar
