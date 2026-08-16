#!/usr/bin/env python3
"""Sube el video terminado a YouTube en el canal correcto, con miniatura y
metadata, y lo programa para publicar. Usa las credenciales OAuth propias
del canal (client_secret_file / token_file en channels/[canal].json).

Requiere que el canal ya haya sido autorizado una vez con
scripts/authorize_channel.py (ese paso genera el token_file).
"""
import argparse
import json
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]
ROOT = Path(__file__).resolve().parent.parent


def cargar_canal(channel_key: str) -> dict:
    return json.loads((ROOT / "channels" / f"{channel_key}.json").read_text())


def obtener_credenciales(canal: dict) -> Credentials:
    token_file = ROOT / canal["youtube"]["token_file"]
    if not token_file.exists():
        raise RuntimeError(
            f"No hay token para este canal. Corre primero: "
            f"python scripts/authorize_channel.py {canal['channel_key']} --step url"
        )

    creds = Credentials.from_authorized_user_file(str(token_file), SCOPES)
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            token_file.write_text(creds.to_json())
        else:
            raise RuntimeError(
                f"Token inválido y sin refresh_token. Vuelve a autorizar el canal: "
                f"python scripts/authorize_channel.py {canal['channel_key']} --step url"
            )
    return creds


def subir_video(channel_key: str, video_path: Path, thumbnail_path: Path, metadata: dict, publish_at_iso: str) -> str:
    canal = cargar_canal(channel_key)
    creds = obtener_credenciales(canal)
    youtube = build("youtube", "v3", credentials=creds)

    body = {
        "snippet": {
            "title": metadata["title"],
            "description": metadata["description"],
            "tags": metadata.get("tags", []),
            "categoryId": canal["youtube"]["default_category_id"],
        },
        "status": {
            "privacyStatus": "private",
            "publishAt": publish_at_iso,
            "selfDeclaredMadeForKids": canal["youtube"]["made_for_kids"],
        },
    }
    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=MediaFileUpload(str(video_path), chunksize=-1, resumable=True),
    )
    response = request.execute()
    video_id = response["id"]

    youtube.thumbnails().set(videoId=video_id, media_body=MediaFileUpload(str(thumbnail_path))).execute()
    return video_id


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("channel_key")
    p.add_argument("video_path")
    p.add_argument("--thumbnail", required=True)
    p.add_argument("--metadata-file", required=True)
    p.add_argument("--publish-at", required=True, help="ISO 8601, ej. 2026-08-20T15:00:00Z")
    args = p.parse_args()
    metadata = json.loads(Path(args.metadata_file).read_text())
    video_id = subir_video(args.channel_key, Path(args.video_path), Path(args.thumbnail), metadata, args.publish_at)
    print(f"Subido: https://youtube.com/watch?v={video_id}")


if __name__ == "__main__":
    main()
