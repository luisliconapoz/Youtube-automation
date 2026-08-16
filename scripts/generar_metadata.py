#!/usr/bin/env python3
"""Genera título, descripción y tags optimizados para un video, según el
`metadata_style` definido en channels/[canal].json.

TODO: implementar una vez definido el estilo de título/descripción/tags de
cada canal con el usuario.
"""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def cargar_canal(channel_key: str) -> dict:
    return json.loads((ROOT / "channels" / f"{channel_key}.json").read_text())


def generar_metadata(channel_key: str, tema: str, guion: str) -> dict:
    canal = cargar_canal(channel_key)
    raise NotImplementedError(
        f"Falta implementar metadata_style para '{channel_key}'"
    )


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("channel_key")
    p.add_argument("--tema", required=True)
    p.add_argument("--guion-file", required=True)
    args = p.parse_args()
    guion = Path(args.guion_file).read_text()
    meta = generar_metadata(args.channel_key, args.tema, guion)
    print(json.dumps(meta, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
