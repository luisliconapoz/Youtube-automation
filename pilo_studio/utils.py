"""Utilidades compartidas."""

from __future__ import annotations

import hashlib
import json
import logging
import re
import shutil
import subprocess
import unicodedata
from pathlib import Path

log = logging.getLogger("pilo")


def slug(texto: str) -> str:
    t = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-zA-Z0-9]+", "-", t).strip("-").lower() or "video"


def semilla(texto: str) -> int:
    """Semilla determinista: mismo proyecto => mismo 'look' en todas las imágenes."""
    return int(hashlib.sha256(texto.encode()).hexdigest()[:8], 16) % 2_147_483_647


def ffmpeg_bin() -> str:
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    import imageio_ffmpeg  # dependencia de moviepy, trae un binario propio

    return imageio_ffmpeg.get_ffmpeg_exe()


def duracion_media(ruta: Path) -> float:
    """Duración de un archivo de audio/video vía ffprobe (o ffmpeg como respaldo)."""
    ffprobe = shutil.which("ffprobe")
    if ffprobe:
        out = subprocess.run(
            [ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "json", str(ruta)],
            capture_output=True, text=True, check=True,
        ).stdout
        return float(json.loads(out)["format"]["duration"])
    proc = subprocess.run([ffmpeg_bin(), "-i", str(ruta)], capture_output=True, text=True)
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", proc.stderr)
    if not m:
        raise RuntimeError(f"No se pudo leer la duración de {ruta}")
    h, mi, s = m.groups()
    return int(h) * 3600 + int(mi) * 60 + float(s)


def ejecutar(cmd: list[str], cwd: Path | None = None) -> None:
    log.debug("$ %s", " ".join(cmd))
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    if proc.returncode != 0:
        raise RuntimeError(f"Falló: {' '.join(cmd[:3])}…\n{proc.stderr[-2000:]}")
