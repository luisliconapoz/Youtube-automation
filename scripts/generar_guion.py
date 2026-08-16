#!/usr/bin/env python3
"""Genera el guion final de un video a partir del tema/idea dado por el usuario.

TODO: implementar una vez definida la estructura de guion exacta de cada
formato (versus vs. top5) con el usuario.
"""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def cargar_canal(channel_key: str) -> dict:
    return json.loads((ROOT / "channels" / f"{channel_key}.json").read_text())


def generar_guion(channel_key: str, video_dir: Path, tema: str) -> str:
    canal = cargar_canal(channel_key)
    raise NotImplementedError(
        f"Falta implementar generación de guion para formato '{canal['format']}'"
    )


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("channel_key")
    p.add_argument("video_dir")
    p.add_argument("--tema", required=True)
    args = p.parse_args()
    guion = generar_guion(args.channel_key, Path(args.video_dir), args.tema)
    print(guion)


if __name__ == "__main__":
    main()
