#!/usr/bin/env python3
"""Orquesta el flujo completo de un video, de principio a fin:

  1. Lee clips_raw/[canal]/[video]/ (+ guion.txt si existe)
  2. generar_guion.py     -> guion final
  3. editar_video.py      -> output/[canal]/[video].mp4
  4. generar_thumbnail.py -> thumbnails/[canal]/[video].jpg
  5. generar_metadata.py  -> título/descripción/tags
  6. subir_youtube.py     -> sube + programa en YouTube
  7. notion_sync.py       -> actualiza estado en Notion

Uso:
    python scripts/pipeline.py CANAL NOMBRE_VIDEO --tema "..." --publish-at 2026-08-20T15:00:00Z

TODO: activar cada paso a medida que su script correspondiente esté
implementado (dependen de: credenciales YouTube de los 4 canales,
especificación visual de cada plantilla, y esquema de la base de Notion).
"""
import argparse
import json
from pathlib import Path

import generar_guion
import generar_metadata
import editar_video
import generar_thumbnail
import subir_youtube
import notion_sync

ROOT = Path(__file__).resolve().parent.parent


def run(channel_key: str, video_nombre: str, tema: str, publish_at: str) -> None:
    video_dir = ROOT / "clips_raw" / channel_key / video_nombre
    if not video_dir.is_dir():
        raise FileNotFoundError(f"No existe {video_dir}")

    guion_path = video_dir / "guion.txt"
    if guion_path.exists() and guion_path.read_text().strip():
        guion = guion_path.read_text()
    else:
        guion = generar_guion.generar_guion(channel_key, video_dir, tema)
        guion_path.write_text(guion)
    notion_sync.actualizar_estado(channel_key, video_nombre, "Guion listo")

    output_path = ROOT / "output" / channel_key / f"{video_nombre}.mp4"
    editar_video.editar_video(channel_key, video_dir, guion_path, output_path)

    thumbnail_path = ROOT / "thumbnails" / channel_key / f"{video_nombre}.jpg"
    metadata = generar_metadata.generar_metadata(channel_key, tema, guion)
    generar_thumbnail.generar_thumbnail(channel_key, output_path, metadata["title"], thumbnail_path)
    notion_sync.actualizar_estado(channel_key, video_nombre, "Editado")

    subir_youtube.subir_video(channel_key, output_path, thumbnail_path, metadata, publish_at)
    notion_sync.actualizar_estado(channel_key, video_nombre, "Publicado")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("channel_key")
    p.add_argument("video_nombre")
    p.add_argument("--tema", required=True)
    p.add_argument("--publish-at", required=True, help="ISO 8601, ej. 2026-08-20T15:00:00Z")
    args = p.parse_args()
    run(args.channel_key, args.video_nombre, args.tema, args.publish_at)


if __name__ == "__main__":
    main()
