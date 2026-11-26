#!/usr/bin/env bash
# Prueba de producción 01 · reproduce todo el video desde cero (gratis, local).
set -euo pipefail
cd "$(dirname "$0")/.."
pip install -q kokoro-onnx soundfile pillow numpy
mkdir -p modelos
for f in kokoro-v1.0.onnx voices-v1.0.bin; do
  [ -s "modelos/$f" ] || curl -sSL --fail -o "modelos/$f" \
    "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/$f"
done
python3 scripts/01_voz.py modelos      # narración  → audio/
python3 scripts/02_montaje.py          # imágenes + montaje → imagenes/, salida/
python3 scripts/03_verificar.py        # verificación técnica
