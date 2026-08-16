#!/usr/bin/env python3
"""Actualiza el estado de un video en la base de producción de Notion:
Pendiente -> Guion listo -> Editado -> Publicado.

TODO: implementar una vez el usuario comparta el ID de la base de datos de
Notion y el esquema de sus propiedades (nombre de la columna de estado,
nombre de la columna que identifica el video/canal, etc.).
"""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

ESTADOS = ["Pendiente", "Guion listo", "Editado", "Publicado"]


def cargar_canal(channel_key: str) -> dict:
    return json.loads((ROOT / "channels" / f"{channel_key}.json").read_text())


def actualizar_estado(channel_key: str, video_nombre: str, estado: str) -> None:
    if estado not in ESTADOS:
        raise ValueError(f"Estado inválido: {estado}. Debe ser uno de {ESTADOS}")
    canal = cargar_canal(channel_key)
    database_id = canal["notion"]["database_id"]
    raise NotImplementedError("Falta configurar integración de Notion y database_id")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("channel_key")
    p.add_argument("video_nombre")
    p.add_argument("estado", choices=ESTADOS)
    args = p.parse_args()
    actualizar_estado(args.channel_key, args.video_nombre, args.estado)


if __name__ == "__main__":
    main()
