#!/usr/bin/env bash
# Se ejecuta una sola vez al crear el Codespace.
set -euo pipefail
sudo apt-get update
sudo apt-get install -y --no-install-recommends ffmpeg rclone fonts-dejavu-core
pip install --upgrade pip
pip install -r requirements-dev.txt
echo "✅ Pilo Studio listo. Ejecuta: python pilo.py"
