#!/usr/bin/env bash
# Publica la app en un Hugging Face Space (SDK Docker).
#   scripts/publicar_hf.sh USUARIO_HF NOMBRE_DEL_SPACE
# Pide usuario y contraseña de Git: usuario = tu usuario de Hugging Face, contraseña = un token con permiso de escritura.
# Reemplaza TODO el contenido del Space (es un repositorio aparte del de GitHub).
set -euo pipefail
[ $# -eq 2 ] || { echo "Uso: $0 USUARIO_HF NOMBRE_DEL_SPACE"; exit 1; }
USUARIO="$1"; SPACE="$2"
RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp -d)"
git -C "$RAIZ" archive HEAD | tar -x -C "$TMP"       # solo lo que está commiteado
{
  printf -- '---\ntitle: Detector EPP en obra\nemoji: 🦺\ncolorFrom: blue\ncolorTo: green\nsdk: docker\napp_port: 7860\npinned: false\n---\n\n'
  cat "$TMP/README.md"
} > "$TMP/README.hf" && mv "$TMP/README.hf" "$TMP/README.md"
cd "$TMP"
git init -q -b main
git add -A
git -c user.name="$USUARIO" -c user.email="$USUARIO@users.noreply.huggingface.co" commit -q -m "Despliegue de la app de detección de EPP"
git -c credential.helper= push --force "https://huggingface.co/spaces/$USUARIO/$SPACE" main
echo "Listo. Estado y registros: https://huggingface.co/spaces/$USUARIO/$SPACE"
echo "URL de la app (usar esta, no la página de huggingface.co): https://${USUARIO,,}-${SPACE,,}.hf.space"
