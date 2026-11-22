"""FASE 3 — Generación de imágenes con consistencia visual.

Cadena de respaldo configurable (todas gratuitas, todas en la nube):
  pollinations -> Pollinations.ai (Flux). Sin clave funciona con límite de velocidad;
                  con POLLINATIONS_API_KEY (registro gratuito) va más rápido.
  huggingface  -> Inference API gratuita de Hugging Face (FLUX.1-schnell), requiere HF_TOKEN
  referencias  -> reutiliza las imágenes de referencia del usuario
  placeholder  -> degradado con la paleta del proyecto + texto (siempre funciona)
"""

from __future__ import annotations

import io
import os
import time
import urllib.parse
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

from pilo_studio.models import Escena, Guion
from pilo_studio.utils import log
from pilo_studio.visuals.estilo import BibliaEstilo


def _ajustar(img: Image.Image, ancho: int, alto: int) -> Image.Image:
    """Recorta/escala para cubrir exactamente el cuadro (sin bandas negras)."""
    return ImageOps.fit(img.convert("RGB"), (ancho, alto), Image.Resampling.LANCZOS)


# ------------------------------------------------------------ pollinations
_ULTIMA_POLLINATIONS = 0.0


def pollinations(prompt: str, ancho: int, alto: int, semilla: int, cfg: dict) -> Image.Image | None:
    global _ULTIMA_POLLINATIONS
    pc = cfg["imagenes"]["pollinations"]
    clave = os.environ.get("POLLINATIONS_API_KEY")
    url = "https://image.pollinations.ai/prompt/" + urllib.parse.quote(prompt[:1500])
    params = {"width": ancho, "height": alto, "seed": semilla, "model": pc.get("modelo", "flux"),
              "nologo": "true", "enhance": "false", "negative": cfg["imagenes"].get("negativo", "")}
    cabeceras = {"Authorization": f"Bearer {clave}"} if clave else {}
    # Sin clave el nivel anónimo admite ~1 petición cada 15 s: respetarlo evita bloqueos
    espera = 0 if clave else float(pc.get("espera_anonimo", 16))
    for intento in range(1, pc.get("reintentos", 3) + 1):
        pausa = _ULTIMA_POLLINATIONS + espera - time.time()
        if pausa > 0:
            time.sleep(pausa)
        try:
            r = requests.get(url, params=params, headers=cabeceras, timeout=pc.get("timeout", 120))
            _ULTIMA_POLLINATIONS = time.time()
            if r.ok and r.headers.get("content-type", "").startswith("image"):
                return Image.open(io.BytesIO(r.content))
            log.warning("Pollinations HTTP %s (intento %d)", r.status_code, intento)
        except requests.RequestException as e:
            _ULTIMA_POLLINATIONS = time.time()
            log.warning("Pollinations no disponible (intento %d): %s", intento, type(e).__name__)
        time.sleep(3 * intento)
    return None


# ------------------------------------------------------------ huggingface
def huggingface(prompt: str, ancho: int, alto: int, semilla: int, cfg: dict) -> Image.Image | None:
    token = os.environ.get("HF_TOKEN")
    if not token:
        return None
    hc = cfg["imagenes"]["huggingface"]
    url = f"https://router.huggingface.co/hf-inference/models/{hc.get('modelo', 'black-forest-labs/FLUX.1-schnell')}"
    # FLUX trabaja mejor en múltiplos de 64 y ~1 MP; luego se reescala al cuadro final
    w, h = (1024, 576) if ancho > alto else (576, 1024)
    try:
        r = requests.post(url, headers={"Authorization": f"Bearer {token}"}, timeout=hc.get("timeout", 120),
                          json={"inputs": prompt, "parameters": {"width": w, "height": h, "seed": semilla}})
    except requests.RequestException as e:
        log.warning("Hugging Face no disponible: %s", type(e).__name__)
        return None
    if r.ok and r.headers.get("content-type", "").startswith("image"):
        return Image.open(io.BytesIO(r.content))
    log.warning("Hugging Face HTTP %s: %s", r.status_code, r.text[:200])
    return None


# ------------------------------------------------------------ referencias
def desde_referencias(biblia: BibliaEstilo, escena: Escena) -> Image.Image | None:
    refs = biblia.proyecto.referencias
    if not refs:
        return None
    # Preferir una referencia cuyo nombre de archivo coincida con un personaje/escenario
    claves = [c.lower() for c in escena.personajes + ([escena.escenario] if escena.escenario else [])]
    for r in refs:
        if any(c in r.stem.lower() for c in claves):
            return Image.open(r)
    return Image.open(refs[(escena.id - 1) % len(refs)])


# ------------------------------------------------------------ placeholder
def _hex(c: str) -> tuple[int, int, int]:
    c = c.lstrip("#")
    return tuple(int(c[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def placeholder(biblia: BibliaEstilo, escena: Escena, ancho: int, alto: int) -> Image.Image:
    paleta = [_hex(c) for c in (biblia.paleta or ["#1d3557", "#457b9d", "#e63946"])]
    a, b = paleta[escena.id % len(paleta)], paleta[(escena.id + 1) % len(paleta)]
    img = Image.new("RGB", (ancho, alto))
    d = ImageDraw.Draw(img)
    for y in range(alto):
        t = y / alto
        d.line([(0, y), (ancho, y)], fill=tuple(int(a[i] * (1 - t) + b[i] * t) for i in range(3)))
    img = img.filter(ImageFilter.GaussianBlur(2))
    d = ImageDraw.Draw(img)
    try:
        fuente = ImageFont.truetype("DejaVuSans-Bold.ttf", max(ancho, alto) // 30)
    except OSError:
        fuente = ImageFont.load_default()
    d.text((ancho // 2, alto // 3), f"Escena {escena.id}", fill="white", font=fuente, anchor="mm")
    return img


# ------------------------------------------------------------ orquestación
def generar_imagenes(guion: Guion, build: Path, cfg: dict, biblia: BibliaEstilo) -> Guion:
    fmt = cfg["formatos"][guion.formato]
    ancho, alto = fmt["ancho"], fmt["alto"]
    destino = build / "imagenes"
    destino.mkdir(parents=True, exist_ok=True)

    for e in guion.escenas:
        ruta = destino / f"escena_{e.id:03d}.png"
        if ruta.exists():
            e.imagen = str(ruta)
            continue
        prompt = biblia.prompt_final(e)
        img, origen = None, None
        for prov in cfg["imagenes"]["proveedores"]:
            if prov == "pollinations":
                img = pollinations(prompt, ancho, alto, biblia.semilla, cfg)
            elif prov == "huggingface":
                img = huggingface(prompt, ancho, alto, biblia.semilla, cfg)
            elif prov == "referencias":
                img = desde_referencias(biblia, e)
            elif prov == "placeholder":
                img = placeholder(biblia, e, ancho, alto)
            if img is not None:
                origen = prov
                break
        if img is None:
            img, origen = placeholder(biblia, e, ancho, alto), "placeholder"
        _ajustar(img, ancho, alto).save(ruta)
        (destino / f"escena_{e.id:03d}.prompt.txt").write_text(prompt, encoding="utf-8")
        e.imagen = str(ruta)
        log.info("  🖼  escena %d vía %s", e.id, origen)
    return guion
