"""Reconstrucción fiel de los personajes a partir de las guías oficiales (Google Flow).

Procedimiento: cada forma se mide sobre la guía original (coordenadas en píxeles de la
guía, recorte indicado en REFERENCIAS) y se dibuja por código con esas mismas
coordenadas. El contorno neón no se dibuja forma por forma: se calcula sobre la
silueta unida (cabeza + cuello + torso + brazos + manos + mechón), igual que en la
guía, donde todo el cuerpo es un único trazo continuo.

Por ahora solo está BLUE (prueba de fidelidad pedida por el director).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

RAIZ = Path(__file__).resolve().parents[2]

# Recorte de la guía donde se midió cada personaje: (archivo, caja x0, y0, x1, y1)
REFERENCIAS = {
    "blue": ("proyectos/fact-stick/guia/guia_oficial.jpg", (15, 150, 240, 400)),
}

NEGRO = (0, 0, 0)
BLANCO = (255, 255, 255)
ROJO_LENGUA = (232, 22, 38)

# ───────────────────── CARA MAESTRA (medida sobre Blue en la guía) ─────────────────────
# Coordenadas relativas al centro de la cabeza (107.3, 68 en el recorte de Blue),
# medidas sobre los píxeles blancos, negros y rojos de la guía.
CARA = {
    "ojo_izq":    dict(c=(5.6, 0.0), rx=9.0, ry=14.2),
    "ojo_der":    dict(c=(35.6, -1.2), rx=7.9, ry=12.2),
    "pupila_izq": dict(c=(12.8, 0.8), r=5.9),
    "pupila_der": dict(c=(41.8, 0.0), r=5.2),
    # cejas: trazos finos en cian oscuro, apenas visibles en la guía
    "ceja_izq":   [(-3.0, -20.0), (1.5, -23.0), (7.0, -23.5)],
    "ceja_der":   [(30.0, -22.5), (34.5, -23.5), (39.0, -21.5)],
    # boca: banda blanca curva (borde superior y borde inferior) + lengua roja
    "boca_sup":   [(2.0, 21.0), (8.0, 22.4), (14.0, 22.6), (20.0, 21.6), (25.0, 19.6)],
    "boca_inf":   [(25.0, 19.6), (20.0, 24.2), (14.0, 25.4), (8.0, 25.0), (2.0, 21.0)],
    # lengua: forma inclinada, más baja a la izquierda (medida en la guía)
    "lengua":     [(1.0, 27.5), (8.0, 26.5), (15.0, 27.5), (17.0, 30.5), (13.0, 34.5), (6.0, 36.5), (0.5, 35.0), (-1.5, 31.0)],
}
GROSOR_CEJA = 1.4


# ───────────────────── BLUE · pose de la guía ("explicando") ─────────────────────
BLUE = {
    "color": (30, 215, 255),
    "trazo": 3.8,                      # grosor del neón en px de guía
    "cabeza": dict(c=(107.3, 68.0), rx=50.0, ry=46.0),
    # mechón: dos puntas cerradas que salen de la parte superior derecha de la cabeza
    "mechon": [(113, 25), (144, 9), (136, 25), (161, 37), (147, 38), (141, 34), (128, 33)],
    "cuello": [(90, 100), (117, 100), (119, 115), (89, 115)],
    "torso": [(89, 113), (118, 113), (125, 118), (123, 215), (78, 215), (77, 118)],
    # brazos: (puntos de la línea central, ancho en cada punto) — ancho entre contornos
    "brazos": [
        ([(74, 126), (59, 139), (45, 153), (55, 170), (65, 183)], [19, 20, 21, 18, 15]),     # en jarra
        ([(119, 123), (132, 143), (147, 160), (162, 148), (176, 140)], [17, 17, 18, 20, 20]),  # extendido
    ],
    "puno": dict(c=(72, 188), r=10.5),
    # mano abierta tipo manopla: contorno exterior + pulgar; los dedos se marcan con
    # líneas interiores, como en la guía
    "palma": [(172, 138), (182, 130), (200, 129), (207, 129), (210, 133), (209, 145), (203, 149), (186, 151), (174, 149)],
    "dedos": [((176, 136), (178, 113), 8.0)],                    # pulgar (desde, hasta, ancho)
    "lineas_mano": [[(190, 134), (201, 133)], [(191, 139), (203, 139)], [(190, 144), (200, 145)],
                    [(174, 140), (177, 143), (181, 142)]],       # separación de dedos + pliegue de la palma
    "piernas": [([(90, 200), (86, 240)], 22), ([(113, 200), (117, 240)], 20)],
    "entrepierna": (103, 198),
}


def _tubo(d: ImageDraw.ImageDraw, pts, anchos, k, fill):
    """Tubo de ancho variable: segmentos + círculos en cada vértice."""
    q = [(x * k, y * k) for x, y in pts]
    if isinstance(anchos, (int, float)):
        anchos = [anchos] * len(pts)
    for (a, b), w0, w1 in zip(zip(q, q[1:]), anchos, anchos[1:]):
        w = (w0 + w1) / 2 * k
        d.line([a, b], fill=fill, width=max(1, int(round(w))))
    for (x, y), w in zip(q, anchos):
        r = w * k / 2
        d.ellipse([x - r, y - r, x + r, y + r], fill=fill)


def _elipse(d, c, rx, ry, k, fill):
    d.ellipse([(c[0] - rx) * k, (c[1] - ry) * k, (c[0] + rx) * k, (c[1] + ry) * k], fill=fill)


def _silueta(diseno, W, H, k) -> Image.Image:
    """Máscara (L) de la silueta unida del personaje: cada forma es la LÍNEA CENTRAL del neón."""
    m = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(m)
    cab = diseno["cabeza"]
    _elipse(d, cab["c"], cab["rx"], cab["ry"], k, 255)
    for clave in ("mechon", "cuello", "torso", "palma"):
        d.polygon([(x * k, y * k) for x, y in diseno[clave]], fill=255)
    for pts, anchos in diseno["brazos"]:
        _tubo(d, pts, anchos, k, 255)
    p = diseno["puno"]
    _elipse(d, p["c"], p["r"], p["r"], k, 255)
    for a, b, w in diseno["dedos"]:
        _tubo(d, [a, b], w, k, 255)
    for pts, w in diseno["piernas"]:
        _tubo(d, pts, w, k, 255)
    ex, ey = diseno["entrepierna"]   # separación entre piernas (la "Λ" de la guía)
    d.polygon([((ex - 5) * k, (ey + 40) * k), (ex * k, ey * k), ((ex + 5) * k, (ey + 40) * k)], fill=0)
    return m


def _desplazar(m: Image.Image, px: float) -> Image.Image:
    """Dilata (px>0) o erosiona (px<0) una máscara con un núcleo redondo aproximado
    (desenfoque gaussiano + umbral): bordes suaves como el neón de la guía."""
    sigma = max(0.5, abs(px) / 2.05)
    b = np.asarray(m.filter(ImageFilter.GaussianBlur(sigma)), dtype=np.float32)
    umbral = 5 if px > 0 else 250
    return Image.fromarray(((b > umbral) * 255).astype("uint8"))


def dibujar_cara(d: ImageDraw.ImageDraw, centro, k, sonda: bool = False):
    """Cara maestra de las guías (medida sobre Blue). Común para todos los personajes."""
    cx, cy = centro

    def P(x, y):
        return ((cx + x) * k, (cy + y) * k)

    for lado in ("izq", "der"):
        o, p = CARA[f"ojo_{lado}"], CARA[f"pupila_{lado}"]
        ox, oy = cx + o["c"][0], cy + o["c"][1]
        _elipse(d, (ox, oy), o["rx"], o["ry"], k, BLANCO)
        if not sonda:
            # pupila recortada por el borde del ojo (efecto "C" de la guía)
            capa = Image.new("L", d.im.size, 0)
            dc = ImageDraw.Draw(capa)
            _elipse(dc, (ox, oy), o["rx"], o["ry"], k, 255)
            pupila = Image.new("L", d.im.size, 0)
            dp = ImageDraw.Draw(pupila)
            _elipse(dp, (cx + p["c"][0], cy + p["c"][1]), p["r"], p["r"], k, 255)
            d.bitmap((0, 0), ImageChops.multiply(capa, pupila), fill=NEGRO)
    ceja = (0, 95, 120)
    for lado in ("izq", "der"):
        d.line([P(*q) for q in CARA[f"ceja_{lado}"]], fill=ceja, width=max(1, int(GROSOR_CEJA * k)), joint="curve")
    d.polygon([P(*q) for q in CARA["boca_sup"] + CARA["boca_inf"][1:]], fill=BLANCO)
    d.polygon([P(*q) for q in CARA["lengua"]], fill=ROJO_LENGUA)


def render(diseno=BLUE, k: float = 4.0, caja=(0, 0, 225, 215), brillo: bool = True) -> Image.Image:
    """Dibuja el personaje en coordenadas de la guía escaladas por `k` (RGB sobre negro)."""
    W, H = int((caja[2] - caja[0]) * k), int((caja[3] - caja[1]) * k)
    sil = _silueta(diseno, W, H, k)
    t = diseno["trazo"] * k / 2
    exterior, interior = _desplazar(sil, t), _desplazar(sil, -t)
    neon = ImageChops.subtract(exterior, interior)
    img = Image.new("RGB", (W, H), NEGRO)
    color = Image.new("RGB", (W, H), diseno["color"])
    if brillo:
        for r, a in ((t * 5, 0.35), (t * 2, 0.6)):
            halo = neon.filter(ImageFilter.GaussianBlur(r)).point(lambda v, a=a: int(min(255, v * a * 2)))
            img = Image.composite(color, img, halo)
    img.paste(NEGRO, mask=interior)
    img = Image.composite(color, img, neon)
    d = ImageDraw.Draw(img)
    for linea in diseno.get("lineas_mano", []):
        d.line([(x * k, y * k) for x, y in linea], fill=diseno["color"], width=max(1, int(1.6 * k)), joint="curve")
    dibujar_cara(d, diseno["cabeza"]["c"], k)
    return img
