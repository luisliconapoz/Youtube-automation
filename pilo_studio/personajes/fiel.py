"""Reconstrucción fiel de los personajes a partir de las guías oficiales (Google Flow).

Procedimiento (orden del director, 2026-11-28): nada se interpreta ni se coloca a ojo.
`trazar.py` mide cada personaje sobre su guía original (recorte en REFERENCIAS, analizado
×4) y guarda los datos vectoriales en `personajes/trazados/<clave>.json`: contornos exactos
del trazo neón (con sus variaciones de grosor, nudillos, líneas de dedos y pliegues),
silueta negra del cuerpo, blanco de los ojos, óvalo y pupila ajustados, boca, lengua,
cejas, colores y perfil del halo. Este módulo solo dibuja esos datos con Pillow.
`comparar.py` valida la reconstrucción contra la guía por partes.

Estado: solo BLUE (prueba de fidelidad). Los otros 12 personajes no se tocan hasta su aprobación.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

RAIZ = Path(__file__).resolve().parents[2]

# Recorte de la guía donde se mide cada personaje: (archivo, caja x0, y0, x1, y1)
REFERENCIAS = {
    "blue": ("proyectos/fact-stick/guia/guia_oficial.jpg", (15, 150, 240, 400)),
}

NEGRO = (0, 0, 0)
BLANCO = (255, 255, 255)


# ───────────────────── render desde el trazado medido sobre la guía ─────────────────────
def cargar_trazado(clave: str) -> dict:
    return json.loads((RAIZ / "personajes" / "trazados" / f"{clave}.json").read_text(encoding="utf-8"))


def _poli_mascara(polis, W, H, k, ss=2) -> Image.Image:
    m = Image.new("L", (W * ss, H * ss), 0)
    d = ImageDraw.Draw(m)
    for p in polis:
        d.polygon([(x * k * ss, y * k * ss) for x, y in p["ext"]], fill=255)
        for a in p["agujeros"]:
            d.polygon([(x * k * ss, y * k * ss) for x, y in a], fill=0)
    return m.resize((W, H), Image.LANCZOS)


def _elipse_rotada(cx, cy, a, b, ang, n=72):
    t = math.radians(ang)
    return [(cx + a * math.cos(u) * math.cos(t) - b * math.sin(u) * math.sin(t),
             cy + a * math.cos(u) * math.sin(t) + b * math.sin(u) * math.cos(t))
            for u in (2 * math.pi * i / n for i in range(n))]


def render_trazado(datos: dict | str, k: float = 4.0, alto: float | None = None, brillo: bool = True) -> Image.Image:
    """Dibuja un personaje a partir de sus datos trazados (coordenadas de la guía × k)."""
    if isinstance(datos, str):
        datos = cargar_trazado(datos)
    w, h = datos["lienzo"]
    W, H = int(w * k), int((alto or h) * k)
    color = tuple(datos["color"])
    fondo = np.zeros((H, W, 3), np.float32) + np.array(datos.get("fondo", [0, 0, 0]), np.float32)
    trazo = _poli_mascara(datos["trazo"], W, H, k)
    interior = _poli_mascara(datos["interior"], W, H, k)
    if brillo:
        hr = datos.get("halo_render", dict(s1=1.2, a1=0.5, s2=4.0, a2=0.45))
        luz = np.zeros((H, W), np.float32)
        for s_, a_ in ((hr["s1"], hr["a1"]), (hr["s2"], hr["a2"])):
            luz += a_ * np.asarray(trazo.filter(ImageFilter.GaussianBlur(s_ * k)), np.float32) / 255
        fondo += np.clip(luz, 0, 1)[..., None] * np.array(datos.get("color_halo", color), np.float32)
    img = Image.fromarray(np.clip(fondo, 0, 255).astype("uint8"))
    img.paste(NEGRO, mask=interior)
    img.paste(color, mask=trazo)

    # cara: ojos (elipse ajustada + pupila recortada por el ojo), cejas, boca y lengua
    d = ImageDraw.Draw(img, "RGBA")
    S = 2
    if datos.get("ojos_blanco"):
        # forma exacta del blanco del ojo medida en la guía (la pupila es el negro de la cabeza)
        img.paste(tuple(datos.get("color_blanco", BLANCO)), mask=_poli_mascara(datos["ojos_blanco"], W, H, k))
    for o in ([] if datos.get("ojos_blanco") else datos["ojos"]):
        ojo = Image.new("L", (W * S, H * S), 0)
        ImageDraw.Draw(ojo).polygon([(x * k * S, y * k * S) for x, y in _elipse_rotada(*o["elipse"])], fill=255)
        pup = Image.new("L", (W * S, H * S), 0)
        px, py, pr = o["pupila"]
        ImageDraw.Draw(pup).ellipse([(px - pr) * k * S, (py - pr) * k * S, (px + pr) * k * S, (py + pr) * k * S], fill=255)
        ojo, pup = ojo.resize((W, H), Image.LANCZOS), pup.resize((W, H), Image.LANCZOS)
        img.paste(tuple(datos.get("color_blanco", BLANCO)), mask=ojo)
        img.paste(NEGRO, mask=ImageChops.multiply(ojo, pup))
    for clave, col in (("cejas", "color_ceja"), ("boca", "color_blanco"), ("lengua", "color_lengua")):
        m = _poli_mascara(datos[clave], W, H, k)
        img.paste(tuple(datos.get(col, BLANCO)), mask=m)
    return img
