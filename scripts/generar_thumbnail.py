#!/usr/bin/env python3
"""Genera la miniatura del video con Python + Pillow, siguiendo el
`visual_template` del canal.

TODO: implementar una vez definido el estilo visual de miniatura de cada
canal con el usuario.
"""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def cargar_canal(channel_key: str) -> dict:
    return json.loads((ROOT / "channels" / f"{channel_key}.json").read_text())


def generar_thumbnail(channel_key: str, video_path: Path, titulo: str, output_path: Path) -> Path:
    canal = cargar_canal(channel_key)
    raise NotImplementedError(
        f"Falta implementar generación de thumbnail para '{channel_key}'"
    )


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("channel_key")
    p.add_argument("video_path")
    p.add_argument("--titulo", required=True)
    p.add_argument("--output", required=True)
    args = p.parse_args()
    generar_thumbnail(args.channel_key, Path(args.video_path), args.titulo, Path(args.output))


if __name__ == "__main__":
    main()
