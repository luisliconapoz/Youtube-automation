#!/usr/bin/env python3
"""Edita el video final con ffmpeg: corta/ordena clips, quema subtítulos,
aplica zooms, transiciones y marca de agua/logo, según el `visual_template`
definido en channels/[canal].json.

TODO: implementar una vez definida la especificación visual exacta de cada
plantilla (colores, fuente, posición de logo, timing de zoom/transición).
"""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def cargar_canal(channel_key: str) -> dict:
    return json.loads((ROOT / "channels" / f"{channel_key}.json").read_text())


def editar_video(channel_key: str, video_dir: Path, guion_path: Path, output_path: Path) -> Path:
    canal = cargar_canal(channel_key)
    plantilla = canal["visual_template"]
    raise NotImplementedError(
        f"Falta implementar edición ffmpeg para '{channel_key}' con plantilla {plantilla}"
    )


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("channel_key")
    p.add_argument("video_dir")
    p.add_argument("--guion-file", required=True)
    p.add_argument("--output", required=True)
    args = p.parse_args()
    editar_video(args.channel_key, Path(args.video_dir), Path(args.guion_file), Path(args.output))


if __name__ == "__main__":
    main()
