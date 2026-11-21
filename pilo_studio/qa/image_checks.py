"""QA Gate 2 y 3: chequeos automáticos de imágenes, audio y MP4 final."""
from __future__ import annotations

import json
import shutil
import struct
import subprocess
import wave
from pathlib import Path

from ..core.formats import FormatSpec

BLACK_BORDER_MAX_LUMA = 28     # 0-255: el borde de la imagen debe ser casi negro
BLACK_BORDER_MIN_RATIO = 0.85  # % de píxeles del borde que deben ser "negros"


def _png_size(path: Path) -> tuple[int, int] | None:
    with path.open("rb") as f:
        head = f.read(24)
    if head[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    return struct.unpack(">II", head[16:24])


def check_image(path: Path, fmt: FormatSpec) -> list[str]:
    if not path.exists():
        return ["no existe"]
    try:
        from PIL import Image
    except ImportError:
        Image = None

    if Image is None:
        size = _png_size(path)
        if not size:
            return ["no es PNG válido"]
        w, h = size
        problems = []
    else:
        with Image.open(path) as im:
            w, h = im.size
            gray = im.convert("L")
            small = gray.resize((64, 64 * h // max(w, 1) or 1))
            sw, sh = small.size
            px = small.load()
            border = [px[x, y] for x in range(sw) for y in (0, 1, sh - 2, sh - 1)]
            border += [px[x, y] for y in range(sh) for x in (0, 1, sw - 2, sw - 1)]
            dark = sum(1 for v in border if v <= BLACK_BORDER_MAX_LUMA) / len(border)
        problems = []
        if dark < BLACK_BORDER_MIN_RATIO:
            problems.append(f"fondo no negro (solo {dark:.0%} del borde es negro)")

    target = fmt.width / fmt.height
    if abs(w / h - target) > 0.02:
        problems.append(f"proporción {w}x{h} ≠ {fmt.aspect}")
    min_w = 1280 if fmt.name == "LONG" else 720
    if w < min_w:
        problems.append(f"resolución baja ({w}px de ancho, mínimo {min_w})")
    return problems


def wav_duration(path: Path) -> float | None:
    if not path.exists():
        return None
    try:
        with wave.open(str(path)) as w:
            return w.getnframes() / float(w.getframerate())
    except (wave.Error, EOFError):
        return None


def probe_video(path: Path) -> dict | None:
    if not path.exists() or not shutil.which("ffprobe"):
        return None
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
        capture_output=True, text=True,
    )
    if out.returncode:
        return None
    data = json.loads(out.stdout)
    v = next((s for s in data["streams"] if s["codec_type"] == "video"), None)
    if not v:
        return None
    return {
        "duration": float(data["format"]["duration"]),
        "width": int(v["width"]), "height": int(v["height"]),
        "has_audio": any(s["codec_type"] == "audio" for s in data["streams"]),
    }
