#!/usr/bin/env bash
# Publica la app en un Hugging Face Space (SDK Docker) usando la sesión de `hf auth login`.
#   scripts/publicar_hf.sh USUARIO_HF NOMBRE_DEL_SPACE
# Requisitos: pip install huggingface_hub   y   hf auth login (token con permiso de escritura)
set -euo pipefail
[ $# -eq 2 ] || { echo "Uso: $0 USUARIO_HF NOMBRE_DEL_SPACE"; exit 1; }
USUARIO="$1"; SPACE="$2"
RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
HF="$(command -v hf || true)"; [ -n "$HF" ] || { echo "No encuentro 'hf'. Activa el entorno (source .venv/bin/activate) o ejecuta: pip install huggingface_hub"; exit 1; }
"$HF" auth whoami >/dev/null 2>&1 || { echo "No hay sesión. Ejecuta: hf auth login"; exit 1; }

TMP="$(mktemp -d)"
# solo lo necesario para correr la app (sin docs, demo, resultados ni scripts)
git -C "$RAIZ" archive HEAD Dockerfile requirements-server.txt .dockerignore src db models README.md | tar -x -C "$TMP"
{
  printf -- '---\ntitle: Detector EPP en obra\nemoji: 🦺\ncolorFrom: blue\ncolorTo: green\nsdk: docker\napp_port: 7860\npinned: false\n---\n\n'
  cat "$TMP/README.md"
} > "$TMP/README.hf" && mv "$TMP/README.hf" "$TMP/README.md"

echo "Creando el Space (si no existe)…"
"$HF" repos create "$USUARIO/$SPACE" --repo-type space --space-sdk docker --exist-ok --public
echo "Subiendo archivos…"
"$HF" upload "$USUARIO/$SPACE" "$TMP" . --repo-type space --commit-message "Despliegue de la app de detección de EPP"
echo
echo "Listo. Estado y registros: https://huggingface.co/spaces/$USUARIO/$SPACE"
echo "URL de la app (usar esta, no la página de huggingface.co): https://${USUARIO,,}-${SPACE,,}.hf.space"
echo "Recuerda crear el secreto EPP_CLAVE en Settings → Variables and secrets."
