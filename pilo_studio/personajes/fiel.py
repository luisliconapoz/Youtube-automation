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


def _area_caja(p) -> float:
    e = np.asarray(p["ext"], float)
    return float(np.ptp(e[:, 0]) * np.ptp(e[:, 1])) if len(e) else 0.0


def _poli_mascara(polis, W, H, k, ss=2) -> Image.Image:
    m = Image.new("L", (W * ss, H * ss), 0)
    d = ImageDraw.Draw(m)
    # de mayor a menor: así una forma dentro del hueco de otra (teclas en la calculadora) no se borra
    for p in sorted(polis, key=_area_caja, reverse=True):
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


# ───────────────────── formato por capas (lote de 13) + rostro maestro ─────────────────────
MARGEN_CARA = 1.5      # px de guía: ningún accesorio puede acercarse más a un rasgo facial
EXPRESIONES = ["neutral", "happy", "talking", "surprised", "confused", "thinking",
               "concerned", "skeptical", "excited", "angry", "serious", "smug"]


def _maestro_de_blue(b: dict) -> tuple[dict, dict]:
    """Rostro maestro normalizado (origen = punto medio entre ojos, unidad = distancia entre ojos)."""
    o1, o2 = (np.array(o["elipse"][:2]) for o in b["ojos"])
    medio, dist = (o1 + o2) / 2, float(np.linalg.norm(o2 - o1))
    n = lambda x, y: [(x - medio[0]) / dist, (y - medio[1]) / dist]
    norm = lambda polis: [{"ext": [n(x, y) for x, y in p["ext"]],
                           "agujeros": [[n(x, y) for x, y in a] for a in p["agujeros"]]} for p in polis]
    ojos = [{"elipse": n(*o["elipse"][:2]) + [o["elipse"][2] / dist, o["elipse"][3] / dist, o["elipse"][4]],
             "pupila": n(*o["pupila"][:2]) + [o["pupila"][2] / dist]} for o in b["ojos"]]
    maestro = {"ojos_blanco": norm(b["ojos_blanco"]), "boca": norm(b["boca"]), "lengua": norm(b["lengua"]),
               "cejas": norm(b["cejas"]), "ojos": ojos, "color_blanco": b["color_blanco"],
               "color_lengua": b["color_lengua"], "color_ceja": b["color_ceja"]}
    return maestro, {"medio": medio.tolist(), "escala": dist}


def normalizar(datos: dict) -> dict:
    """Convierte el trazado de Blue (formato de la ronda 2) al formato por capas."""
    if datos.get("formato") == "capas":
        return datos
    maestro, rostro = _maestro_de_blue(datos)
    return {"clave": datos["clave"], "formato": "capas", "lienzo": datos["lienzo"], "fondo": datos["fondo"],
            "capas": [{"color": datos["color"], "color_halo": datos.get("color_halo", datos["color"]),
                       "polis": datos["trazo"]}],
            "interior": datos["interior"], "rostro": rostro, "maestro": maestro,
            "halo_render": datos["halo_render"]}


def cargar(clave: str) -> dict:
    return normalizar(cargar_trazado(clave))


def _transformar(polis, rostro, k):
    (mx, my), s = rostro["medio"], rostro["escala"]
    return [{"ext": [[(mx + x * s) * k, (my + y * s) * k] for x, y in p["ext"]],
             "agujeros": [[[(mx + x * s) * k, (my + y * s) * k] for x, y in a] for a in p["agujeros"]]} for p in polis]


def _mascara_px(polis_px, W, H, ss=2) -> Image.Image:
    m = Image.new("L", (W * ss, H * ss), 0)
    d = ImageDraw.Draw(m)
    for p in sorted(polis_px, key=_area_caja, reverse=True):
        d.polygon([(x * ss, y * ss) for x, y in p["ext"]], fill=255)
        for a in p["agujeros"]:
            d.polygon([(x * ss, y * ss) for x, y in a], fill=0)
    return m.resize((W, H), Image.LANCZOS)


# ── expresiones: todas parten de las medidas del rostro maestro (Blue) ──
# mirada (fracción del radio del ojo), cejas (None = las tenues de la guía; si no: subida e inclinación
# en unidades de distancia entre ojos, dibujadas en blanco) y boca
_EXPR = {
    "neutral":   dict(mirada=(0.0, 0.0),   cejas=None,               boca="sonrisa"),
    "happy":     dict(mirada=None,         cejas=None,               boca="guia"),
    "talking":   dict(mirada=(0.0, 0.0),   cejas=None,               boca="hablar"),
    "surprised": dict(mirada=(0.0, -0.1),  cejas=(0.16, 0.0, 0.0),   boca="o"),
    "confused":  dict(mirada=(-0.3, -0.3), cejas=(0.14, -0.06, 0.06), boca="ondulada"),
    "thinking":  dict(mirada=(0.2, -0.55), cejas=(0.08, 0.0, 0.05),  boca="lateral"),
    "concerned": dict(mirada=(-0.1, 0.25), cejas=(0.06, -0.09, -0.09), boca="triste"),
    "skeptical": dict(mirada=(0.25, 0.0),  cejas=(0.0, 0.07, -0.1),  boca="plana_lado"),
    "excited":   dict(mirada=(0.0, -0.1),  cejas=None,               boca="grande"),
    "angry":     dict(mirada=(0.0, 0.1),   cejas=(-0.04, 0.12, 0.12), boca="dientes"),
    "serious":   dict(mirada=(0.0, 0.0),   cejas=(-0.02, 0.06, 0.06), boca="plana"),
    "smug":      dict(mirada=(0.3, 0.15),  cejas=(-0.03, 0.08, -0.05), boca="sonrisa_lado"),
}


def dibujar_rostro(img: Image.Image, datos: dict, k: float, expresion: str = "happy"):
    """Rostro maestro en la cabeza del personaje. 'happy' es la cara trazada de la guía (exacta)."""
    m, rostro = datos["maestro"], datos["rostro"]
    W, H = img.size
    (mx, my), s = rostro["medio"], rostro["escala"]
    P = lambda x, y: ((mx + x * s) * k, (my + y * s) * k)
    blanco, rojo, ceja = tuple(m["color_blanco"]), tuple(m["color_lengua"]), tuple(m["color_ceja"])
    e = _EXPR[expresion]
    if e["mirada"] is None:
        img.paste(blanco, mask=_mascara_px(_transformar(m["ojos_blanco"], rostro, k), W, H))
    else:
        for o in m["ojos"]:
            ex, ey, a, b, ang = o["elipse"]
            ojo = _mascara_px([{"ext": [list(P(x, y)) for x, y in _elipse_rotada(ex, ey, a, b, ang)], "agujeros": []}], W, H)
            px, py, pr = o["pupila"]
            gx, gy = e["mirada"]
            px, py = px + gx * a, py + gy * b
            pup = _mascara_px([{"ext": [list(P(x, y)) for x, y in _elipse_rotada(px, py, pr, pr, 0)], "agujeros": []}], W, H)
            img.paste(blanco, mask=ojo)
            img.paste(NEGRO, mask=ImageChops.multiply(ojo, pup))
    d = ImageDraw.Draw(img)
    if e["cejas"] is None:
        img.paste(ceja, mask=_mascara_px(_transformar(m["cejas"], rostro, k), W, H))
    else:
        sube, inc_i, inc_d = e["cejas"]
        for o, inc, lado in zip(m["ojos"], (inc_i, inc_d), (-1, 1)):
            ex, ey, a, b, _ = o["elipse"]
            y = ey - b - 0.16 - sube
            x0, x1 = ex - a * 0.9, ex + a * 0.9
            # inclinación: + = extremo interior más bajo (enfado)
            yi, yo = (y + inc, y - inc) if lado == 1 else (y - inc, y + inc)
            d.line([P(x0, yi if lado == 1 else yo), P(x1, yo if lado == 1 else yi)], fill=blanco,
                   width=max(1, int(0.09 * s * k)), joint="curve")
    _boca(img, d, m, rostro, k, e["boca"], P, blanco, rojo)


def _boca(img, d, m, rostro, k, tipo, P, blanco, rojo):
    W, H = img.size
    if tipo == "guia":
        img.paste(blanco, mask=_mascara_px(_transformar(m["boca"], rostro, k), W, H))
        img.paste(rojo, mask=_mascara_px(_transformar(m["lengua"], rostro, k), W, H))
        return
    pts = np.array([q for p in m["boca"] for q in p["ext"]])
    cx, cy = pts[:, 0].mean(), pts[:, 1].mean()
    an = (pts[:, 0].max() - pts[:, 0].min()) / 2
    gr = max(1, int(0.08 * rostro["escala"] * k))
    oscuro = (90, 0, 18)
    def eli(x, y, rx, ry, fill):
        d.ellipse([*P(x - rx, y - ry), *P(x + rx, y + ry)], fill=fill)
    if tipo == "sonrisa":
        d.arc([*P(cx - an * 0.8, cy - 0.25), *P(cx + an * 0.8, cy + 0.08)], 20, 160, fill=blanco, width=gr)
    elif tipo == "hablar":
        eli(cx, cy + 0.06, an * 0.45, 0.16, oscuro)
        eli(cx - 0.03, cy + 0.14, an * 0.28, 0.07, rojo)
    elif tipo == "o":
        eli(cx, cy + 0.06, 0.12, 0.17, oscuro)
        eli(cx, cy + 0.15, 0.07, 0.05, rojo)
    elif tipo == "grande":
        d.chord([*P(cx - an * 1.1, cy - 0.3), *P(cx + an * 1.1, cy + 0.45)], 0, 180, fill=oscuro)
        d.chord([*P(cx - an * 0.6, cy + 0.12), *P(cx + an * 0.3, cy + 0.42)], 180, 360, fill=rojo)
        d.arc([*P(cx - an * 1.1, cy - 0.2), *P(cx + an * 1.1, cy + 0.12)], 15, 165, fill=blanco, width=gr)
    elif tipo == "ondulada":
        d.line([P(cx - an * 0.7 + i * an * 0.35, cy + (0.05 if i % 2 else -0.03)) for i in range(5)],
               fill=blanco, width=gr, joint="curve")
    elif tipo == "lateral":
        d.line([P(cx, cy + 0.05), P(cx + an * 0.6, cy - 0.02)], fill=blanco, width=gr)
    elif tipo == "triste":
        d.arc([*P(cx - an * 0.6, cy + 0.0), *P(cx + an * 0.6, cy + 0.3)], 200, 340, fill=blanco, width=gr)
    elif tipo == "plana":
        d.line([P(cx - an * 0.55, cy + 0.04), P(cx + an * 0.55, cy + 0.04)], fill=blanco, width=gr)
    elif tipo == "plana_lado":
        d.line([P(cx - an * 0.2, cy + 0.06), P(cx + an * 0.7, cy)], fill=blanco, width=gr)
    elif tipo == "dientes":
        d.rounded_rectangle([*P(cx - an * 0.6, cy - 0.06), *P(cx + an * 0.6, cy + 0.16)], radius=gr, fill=blanco)
        d.line([P(cx - an * 0.6, cy + 0.05), P(cx + an * 0.6, cy + 0.05)], fill=NEGRO, width=max(1, gr // 2))
    elif tipo == "sonrisa_lado":
        d.arc([*P(cx - an * 0.2, cy - 0.22), *P(cx + an * 0.9, cy + 0.06)], 20, 150, fill=blanco, width=gr)


def mascara_rostro(datos: dict, k: float, margen: float = 0.0, expresion: str = "happy") -> np.ndarray:
    """Máscara (bool) de los rasgos del rostro maestro colocado, ensanchada `margen` px de guía."""
    w, h = datos["lienzo"]
    W, H = int(round(w * k)), int(round(h * k))
    img = Image.new("RGB", (W, H), NEGRO)
    dibujar_rostro(img, datos, k, expresion)
    m = np.asarray(img).max(2) > 40
    if margen > 0:
        r = int(round(margen * k))
        m = np.asarray(Image.fromarray(m.astype("uint8") * 255).filter(ImageFilter.MaxFilter(2 * r + 1))) > 0
    return m


def render_capas(datos: dict | str, k: float = 4.0, expresion: str = "happy", brillo: bool = True) -> Image.Image:
    """Dibuja un personaje del lote (o Blue) a partir de sus datos trazados."""
    datos = cargar(datos) if isinstance(datos, str) else normalizar(datos)
    w, h = datos["lienzo"]
    W, H = int(round(w * k)), int(round(h * k))
    lienzo = np.zeros((H, W, 3), np.float32) + np.array(datos.get("fondo", [0, 0, 0]), np.float32)
    mascaras = [_poli_mascara(c["polis"], W, H, k) for c in datos["capas"]]
    if brillo:
        hr = datos["halo_render"]
        for c, m in zip(datos["capas"], mascaras):
            luz = np.zeros((H, W), np.float32)
            for s_, a_ in ((hr["s1"], hr["a1"]), (hr["s2"], hr["a2"])):
                luz += a_ * np.asarray(m.filter(ImageFilter.GaussianBlur(s_ * k)), np.float32) / 255
            lienzo += np.clip(luz, 0, 1)[..., None] * np.array(c.get("color_halo", c["color"]), np.float32)
    img = Image.fromarray(np.clip(lienzo, 0, 255).astype("uint8"))
    img.paste(NEGRO, mask=_poli_mascara(datos["interior"], W, H, k))
    for c, m in zip(datos["capas"], mascaras):
        img.paste(tuple(c["color"]), mask=m)
    dibujar_rostro(img, datos, k, expresion)
    return img
