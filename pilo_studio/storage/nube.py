"""Subida a la nube con rclone (open-source): OneDrive, Google Drive, Dropbox…

La configuración de rclone se recibe como secreto `RCLONE_CONF_B64` (el archivo
rclone.conf codificado en base64). Así funciona igual en Codespaces y en
GitHub Actions sin guardar credenciales en el repositorio.
"""

from __future__ import annotations

import base64
import os
import shutil
import subprocess
from pathlib import Path

from pilo_studio.utils import log

RCLONE_CONF = Path.home() / ".config" / "rclone" / "rclone.conf"


def preparar_rclone() -> bool:
    """Deja rclone listo para usar. Devuelve False si no está disponible."""
    if not shutil.which("rclone"):
        log.info("rclone no está instalado; se omite la subida a la nube.")
        return False
    b64 = os.environ.get("RCLONE_CONF_B64", "").strip()
    if b64 and not RCLONE_CONF.exists():
        RCLONE_CONF.parent.mkdir(parents=True, exist_ok=True)
        RCLONE_CONF.write_bytes(base64.b64decode(b64))
        RCLONE_CONF.chmod(0o600)
    if not RCLONE_CONF.exists():
        log.info("No hay configuración de rclone (secreto RCLONE_CONF_B64); se omite la subida a la nube.")
        return False
    return True


def subir(carpeta: Path, destino_remoto: str) -> bool:
    """Copia `carpeta` a `<remoto:ruta>/<nombre de carpeta>`."""
    if not destino_remoto or not preparar_rclone():
        return False
    remoto = destino_remoto.split(":", 1)[0]
    listado = subprocess.run(["rclone", "listremotes"], capture_output=True, text=True).stdout.split()
    if f"{remoto}:" not in listado:
        log.warning("El remoto '%s' no existe en rclone.conf (disponibles: %s).", remoto, listado)
        return False
    objetivo = f"{destino_remoto.rstrip('/')}/{carpeta.name}"
    proc = subprocess.run(["rclone", "copy", str(carpeta), objetivo, "--stats-one-line", "--stats", "30s"],
                          capture_output=True, text=True)
    if proc.returncode != 0:
        log.error("Falló la subida con rclone:\n%s", proc.stderr[-1500:])
        return False
    log.info("☁️  Subido a %s", objetivo)
    return True
