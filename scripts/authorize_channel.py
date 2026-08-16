#!/usr/bin/env python3
"""Autoriza un canal de YouTube para el pipeline.

Genera la URL de consentimiento OAuth, intercambia el código de
autorización por un token, lo guarda en credentials/[canal]_token.json, y
detecta el channel_id real del canal autorizado (lo guarda en
channels/[canal].json).

Uso (dos pasos, porque el flujo corre en un entorno remoto sin navegador
en la misma máquina):

  1) Generar el link de autorización:
       python scripts/authorize_channel.py CANAL --step url

  2) Abrir el link en tu navegador, iniciar sesión con la cuenta de Google,
     seleccionar el canal correcto cuando lo pida, aceptar los permisos.
     Google va a redirigir a http://localhost/?code=... y la página va a
     fallar al cargar — eso es normal, nada corre en tu localhost. Copia esa
     URL completa de la barra de direcciones (o solo el valor de "code") y
     pégala aquí:

       python scripts/authorize_channel.py CANAL --step exchange --code "URL_O_CODIGO"
"""
import argparse
import json
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]
REDIRECT_URI = "http://localhost"
ROOT = Path(__file__).resolve().parent.parent


def canal_path(channel_key: str) -> Path:
    return ROOT / "channels" / f"{channel_key}.json"


def cargar_canal(channel_key: str) -> dict:
    return json.loads(canal_path(channel_key).read_text())


def guardar_canal(channel_key: str, canal: dict) -> None:
    canal_path(channel_key).write_text(json.dumps(canal, ensure_ascii=False, indent=2) + "\n")


def build_flow(canal: dict) -> Flow:
    client_secret_file = ROOT / canal["youtube"]["client_secret_file"]
    return Flow.from_client_secrets_file(
        str(client_secret_file), scopes=SCOPES, redirect_uri=REDIRECT_URI
    )


def paso_url(channel_key: str) -> None:
    canal = cargar_canal(channel_key)
    flow = build_flow(canal)
    auth_url, _ = flow.authorization_url(access_type="offline", prompt="consent")
    print(auth_url)


def extraer_code(valor: str) -> str:
    if valor.startswith("http"):
        qs = parse_qs(urlparse(valor).query)
        if "code" not in qs:
            raise ValueError("No encontré 'code' en la URL pegada")
        return qs["code"][0]
    return valor.strip()


def paso_exchange(channel_key: str, code_o_url: str) -> None:
    canal = cargar_canal(channel_key)
    flow = build_flow(canal)
    code = extraer_code(code_o_url)
    flow.fetch_token(code=code)
    creds = flow.credentials

    token_file = ROOT / canal["youtube"]["token_file"]
    token_file.parent.mkdir(parents=True, exist_ok=True)
    token_file.write_text(creds.to_json())

    youtube = build("youtube", "v3", credentials=creds)
    resp = youtube.channels().list(part="id,snippet", mine=True).execute()
    items = resp.get("items", [])
    if not items:
        raise RuntimeError("La cuenta autorizada no tiene canales visibles")
    channel_id = items[0]["id"]
    channel_title = items[0]["snippet"]["title"]

    canal["youtube"]["channel_id"] = channel_id
    guardar_canal(channel_key, canal)

    print(f"Autorizado. Canal detectado: {channel_title} ({channel_id})")
    print(f"Token guardado en {token_file}")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("channel_key")
    p.add_argument("--step", choices=["url", "exchange"], required=True)
    p.add_argument("--code", help="Requerido para --step exchange: la URL completa a la que redirigió Google, o solo el código")
    args = p.parse_args()

    if args.step == "url":
        paso_url(args.channel_key)
    else:
        if not args.code:
            p.error("--code es requerido para --step exchange")
        paso_exchange(args.channel_key, args.code)


if __name__ == "__main__":
    main()
