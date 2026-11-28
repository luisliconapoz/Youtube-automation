"""Rig universal de personajes de Pilo Studio.

Todos los personajes comparten UNA cara maestra (CABEZA, OJO, PUPILA, CEJA, BOCA).
Las expresiones solo cambian cejas, dirección de las pupilas y boca: nunca la forma,
el tamaño ni la posición de cabeza y ojos. Cada personaje es una "piel": color +
accesorios (personajes/personajes.yaml). Las poses se definen por la posición de
las manos y los pies (cinemática inversa de dos huesos).

Unidades: "u". Origen = suelo entre los pies, y crece hacia abajo. Altura de la
figura de pies a coronilla ≈ 322 u. Se dibuja con supermuestreo (×3) y se reduce
con LANCZOS para obtener bordes suaves.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml
from PIL import Image, ImageDraw, ImageFilter

RAIZ = Path(__file__).resolve().parents[2]
CATALOGO = RAIZ / "personajes" / "personajes.yaml"

# ───────────────────────── CARA MAESTRA (no tocar por personaje) ─────────────────────────
CABEZA = dict(cx=0.0, cy=-262.0, r=60.0, borde=3.6)
OJO = dict(dx=17.0, dy=-8.0, rx=14.0, ry=19.0)            # dos óvalos blancos, simétricos
PUPILA = dict(r=7.5, base=(3.0, 3.0), max_dx=5.0, max_dy=9.0)
CEJA = dict(dy=-36.0, semilargo=10.0, grosor=3.4)
BOCA = dict(dy=27.0)
ROJO_BOCA = (255, 45, 75)
BLANCO = (255, 255, 255)

# Lienzo del sprite (u): x ∈ [-LX, LX], y ∈ [-ARRIBA, ABAJO]
LX, ARRIBA, ABAJO = 185.0, 470.0, 25.0
ALTURA_FIGURA = 322.0
SS = 3  # supermuestreo

# ───────────────────────── EXPRESIONES (12 oficiales) ─────────────────────────
# ceja = (desplazamiento vertical, inclinación: + = extremo interior abajo / enfado)
EXPRESIONES: dict[str, dict] = {
    "neutral":   dict(ci=(0, 0),   cd=(0, 0),   mirada=(0, 0),   boca="sonrisa"),
    "happy":     dict(ci=(-3, -2), cd=(-3, -2), mirada=(0, 0),   boca="sonrisa_abierta"),
    "talking":   dict(ci=(-2, 0),  cd=(-2, 0),  mirada=(0, 0),   boca="hablar"),
    "surprised": dict(ci=(-9, 0),  cd=(-9, 0),  mirada=(0, -2),  boca="o"),
    "confused":  dict(ci=(-8, -3), cd=(1, 4),   mirada=(-3, -4), boca="ondulada"),
    "thinking":  dict(ci=(-6, 0),  cd=(0, 3),   mirada=(5, -9),  boca="lateral"),
    "concerned": dict(ci=(-4, -5), cd=(-4, -5), mirada=(0, 2),   boca="triste"),
    "skeptical": dict(ci=(1, 3),   cd=(-8, -2), mirada=(5, 0),   boca="plana_lado"),
    "excited":   dict(ci=(-9, -2), cd=(-9, -2), mirada=(0, -2),  boca="grande"),
    "angry":     dict(ci=(2, 6),   cd=(2, 6),   mirada=(0, 1),   boca="dientes"),
    "serious":   dict(ci=(1, 3),   cd=(1, 3),   mirada=(0, 0),   boca="plana"),
    "smug":      dict(ci=(1, 3),   cd=(-7, -2), mirada=(5, 1),   boca="sonrisa_lado"),
}

# ───────────────────────── POSES ─────────────────────────
# Mano: (x, y, tipo[, dirección del dedo]) en coordenadas del cuerpo. Tipos:
# abierta | puno | senalar | pulgar. "delante": brazo que se dibuja encima.
HOMBRO = {"L": (-24.0, -194.0), "R": (24.0, -194.0)}
CADERA = {"L": (-13.0, -110.0), "R": (13.0, -110.0)}
BRAZO, ANTEBRAZO, MUSLO, PIERNA = 60.0, 56.0, 54.0, 54.5
POSES: dict[str, dict] = {
    # 8 poses oficiales
    "explicando":       dict(L=(-46, -86, "abierta"), R=(98, -150, "abierta")),
    "senalando":        dict(L=(-46, -86, "abierta"), R=(122, -184, "senalar", (1, 0))),
    "pensando":         dict(L=(16, -146, "puno"), R=(22, -198, "puno"), delante="R"),
    "presentando":      dict(L=(-46, -86, "abierta"), R=(118, -168, "abierta")),
    "preguntando":      dict(L=(-86, -150, "abierta"), R=(86, -150, "abierta")),
    "brazos_cruzados":  dict(L=(26, -158, "puno"), R=(-26, -152, "puno"), delante="R"),
    "pulgar_arriba":    dict(L=(-46, -86, "abierta"), R=(72, -196, "pulgar")),
    "celebrando":       dict(L=(-78, -292, "puno"), R=(78, -292, "puno")),
    # variantes de apoyo (para accesorios y animación)
    "neutral":          dict(L=(-48, -86, "abierta"), R=(48, -86, "abierta")),
    "idea":             dict(L=(-46, -86, "abierta"), R=(96, -246, "senalar", (0, -1))),
    "idea_sosteniendo": dict(L=(-66, -146, "puno"), R=(96, -246, "senalar", (0, -1))),
    "sosteniendo_izq":  dict(L=(-66, -150, "puno"), R=(52, -90, "abierta")),
    "mostrando_ambas":  dict(L=(-76, -206, "puno"), R=(84, -186, "abierta")),
    "mostrando_der":    dict(L=(-46, -86, "abierta"), R=(84, -186, "abierta")),
    "senalando_tableta": dict(L=(24, -168, "senalar", (1, 0)), R=(84, -150, "puno"), delante="L"),
    "rascandose":       dict(L=(-46, -86, "abierta"), R=(58, -300, "abierta")),
}
POSES_OFICIALES = ["explicando", "senalando", "pensando", "presentando",
                   "preguntando", "brazos_cruzados", "pulgar_arriba", "celebrando"]
PIES = ((-26.0, -4.0), (26.0, -4.0))


def hex_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


@lru_cache(maxsize=1)
def catalogo() -> dict[str, dict]:
    datos = yaml.safe_load(CATALOGO.read_text(encoding="utf-8"))["personajes"]
    for clave, p in datos.items():
        p["clave"] = clave
        p["rgb"] = hex_rgb(p["color"])
    return datos


def personajes_de(marca: str) -> list[str]:
    return [k for k, p in catalogo().items() if p["marca"] == marca]


# ───────────────────────── geometría ─────────────────────────
def ik(hombro, objetivo, a, b, lado):
    """Cinemática inversa de dos huesos. Devuelve (codo, mano); el codo va hacia fuera."""
    sx, sy = hombro
    dx, dy = objetivo[0] - sx, objetivo[1] - sy
    d = max(abs(a - b) + 1e-3, min(math.hypot(dx, dy), a + b - 1e-3))
    ang = math.atan2(dy, dx)
    th = math.acos((a * a + d * d - b * b) / (2 * a * d))
    cands = [(sx + a * math.cos(ang + s * th), sy + a * math.sin(ang + s * th)) for s in (1, -1)]
    codo = max(cands, key=lambda c: 0.5 * c[0] * lado + c[1])  # codo hacia fuera y abajo
    return codo, (sx + d * math.cos(ang), sy + d * math.sin(ang))


@dataclass
class Lienzo:
    d: ImageDraw.ImageDraw
    s: float          # px por u
    ox: float         # px del origen
    oy: float

    def p(self, x, y):
        return (self.ox + x * self.s, self.oy + y * self.s)

    def w(self, u):
        return max(1, int(round(u * self.s)))

    def caja(self, x0, y0, x1, y1):
        (a, b), (c, d) = self.p(x0, y0), self.p(x1, y1)
        return [min(a, c), min(b, d), max(a, c), max(b, d)]

    # primitivas
    def tubo(self, pts, ancho, color):
        if ancho <= 0:
            return
        q = [self.p(*pt) for pt in pts]
        self.d.line(q, fill=color, width=self.w(ancho), joint="curve")
        r = ancho * self.s / 2
        for x, y in q:
            self.d.ellipse([x - r, y - r, x + r, y + r], fill=color)

    def circulo(self, x, y, r, fill=None, outline=None, ancho=0):
        self.d.ellipse(self.caja(x - r, y - r, x + r, y + r), fill=fill, outline=outline,
                       width=self.w(ancho) if ancho else 0)

    def elipse(self, x, y, rx, ry, fill=None, outline=None, ancho=0):
        self.d.ellipse(self.caja(x - rx, y - ry, x + rx, y + ry), fill=fill, outline=outline,
                       width=self.w(ancho) if ancho else 0)

    def poli(self, pts, fill=None, outline=None, ancho=0):
        self.d.polygon([self.p(*pt) for pt in pts], fill=fill, outline=outline,
                       width=self.w(ancho) if ancho else 0)

    def linea(self, pts, color, ancho):
        self.d.line([self.p(*pt) for pt in pts], fill=color, width=self.w(ancho), joint="curve")

    def arco(self, x0, y0, x1, y1, a0, a1, color, ancho):
        self.d.arc(self.caja(x0, y0, x1, y1), a0, a1, fill=color, width=self.w(ancho))

    def cuerda(self, x0, y0, x1, y1, a0, a1, fill):
        self.d.chord(self.caja(x0, y0, x1, y1), a0, a1, fill=fill)


NEGRO = (0, 0, 0)
TUBO, BORDE = 12.0, 3.2       # ancho de extremidades y grosor del contorno neón
MANO = 8.5


class Esqueleto:
    """Calcula las posiciones de articulaciones de una pose."""

    def __init__(self, pose: str, dy_cuerpo: float = 0.0):
        cfg = POSES[pose]
        self.pose = pose
        self.delante = cfg.get("delante", "R")
        self.dy = dy_cuerpo
        self.brazos = {}
        for lado, sgn in (("L", -1), ("R", 1)):
            x, y, tipo, *resto = cfg[lado]
            hombro = (HOMBRO[lado][0], HOMBRO[lado][1] + dy_cuerpo)
            codo, mano = ik(hombro, (x, y + dy_cuerpo), BRAZO, ANTEBRAZO, sgn)
            direc = resto[0] if resto else None
            self.brazos[lado] = dict(hombro=hombro, codo=codo, mano=mano, tipo=tipo, dir=direc, lado=sgn)
        self.piernas = {}
        for (lado, sgn), pie in zip((("L", -1), ("R", 1)), PIES):
            cadera = (CADERA[lado][0], CADERA[lado][1] + dy_cuerpo)
            rodilla, tobillo = ik(cadera, pie, MUSLO, PIERNA, sgn)
            self.piernas[lado] = dict(cadera=cadera, rodilla=rodilla, pie=tobillo, lado=sgn)
        self.cabeza = (CABEZA["cx"], CABEZA["cy"] + dy_cuerpo)

    def torso(self):
        dy = self.dy
        return [(-25, -202 + dy), (25, -202 + dy), (19, -106 + dy), (-19, -106 + dy)]


# ───────────────────────── cara maestra ─────────────────────────
def dibujar_cara(L: Lienzo, hx: float, hy: float, expresion: str, boca: str | None = None):
    """Dibuja ojos, pupilas, cejas y boca. Idéntico para los 13 personajes."""
    e = EXPRESIONES[expresion]
    gx = max(-PUPILA["max_dx"], min(PUPILA["max_dx"], PUPILA["base"][0] + e["mirada"][0]))
    gy = max(-PUPILA["max_dy"], min(PUPILA["max_dy"], PUPILA["base"][1] + e["mirada"][1]))
    for sgn, (cdy, incl) in ((-1, e["ci"]), (1, e["cd"])):
        ex, ey = hx + sgn * OJO["dx"], hy + OJO["dy"]
        L.elipse(ex, ey, OJO["rx"], OJO["ry"], fill=BLANCO)
        L.circulo(ex + gx, ey + gy, PUPILA["r"], fill=NEGRO)
        by = hy + CEJA["dy"] + cdy
        interior, exterior = ex - sgn * CEJA["semilargo"], ex + sgn * CEJA["semilargo"]
        L.tubo([(exterior, by - incl / 2), (interior, by + incl / 2)], CEJA["grosor"], BLANCO)
    dibujar_boca(L, hx, hy + BOCA["dy"], boca or e["boca"])


def dibujar_boca(L: Lienzo, x, y, tipo):
    g = 3.0
    if tipo == "sonrisa":
        L.arco(x - 12, y - 9, x + 12, y + 7, 25, 155, BLANCO, g)
    elif tipo == "sonrisa_abierta":
        L.cuerda(x - 14, y - 9, x + 14, y + 11, 0, 180, ROJO_BOCA)
    elif tipo == "hablar":
        L.elipse(x, y + 1, 9, 7, fill=ROJO_BOCA)
    elif tipo == "o":
        L.elipse(x, y + 1, 6.5, 8.5, fill=ROJO_BOCA)
    elif tipo == "grande":
        L.cuerda(x - 18, y - 11, x + 18, y + 15, 0, 180, ROJO_BOCA)
        L.d.rectangle(L.caja(x - 15, y + 2, x + 15, y + 5), fill=BLANCO)
    elif tipo == "ondulada":
        L.linea([(x - 12, y + 2), (x - 6, y - 2), (x, y + 2), (x + 6, y - 2), (x + 12, y + 2)], BLANCO, g)
    elif tipo == "lateral":
        L.tubo([(x + 1, y + 2), (x + 12, y - 1)], g, BLANCO)
    elif tipo == "triste":
        L.arco(x - 11, y + 1, x + 11, y + 15, 205, 335, BLANCO, g)
    elif tipo == "plana":
        L.tubo([(x - 10, y + 2), (x + 10, y + 2)], g, BLANCO)
    elif tipo == "plana_lado":
        L.tubo([(x - 4, y + 3), (x + 13, y)], g, BLANCO)
    elif tipo == "dientes":
        L.d.rounded_rectangle(L.caja(x - 12, y - 4, x + 12, y + 7), radius=L.w(3), fill=BLANCO)
        L.linea([(x - 12, y + 1.5), (x + 12, y + 1.5)], NEGRO, 1.4)
        for k in (-6, 0, 6):
            L.linea([(x + k, y - 4), (x + k, y + 7)], NEGRO, 1.2)
    elif tipo == "sonrisa_lado":
        L.arco(x - 5, y - 8, x + 17, y + 6, 20, 150, BLANCO, g)
    else:
        raise ValueError(f"boca desconocida: {tipo}")


# ───────────────────────── accesorios ─────────────────────────
# capa: detras | cuerpo | objeto | cabeza
def _mano(esq, lado):
    return esq.brazos[lado]["mano"]


def acc_mechon(L, esq, c):
    hx, hy = esq.cabeza
    top = hy - CABEZA["r"]
    for dx, cx, cy, ex, ey in ((-6, -2, -22, 6, -30), (2, 10, -24, 18, -26), (10, 20, -14, 26, -12)):
        L.linea([(hx + dx, top + 3), (hx + cx, top + cy), (hx + ex, top + ey)], c, 3.6)


Y_TOCADO = -52.0   # línea (relativa al centro de la cabeza) bajo la cual ningún tocado puede bajar


def _casquete(L, hx, hy, c, extra=3.0, y_corte=Y_TOCADO):
    """Casquete sobre la cabeza, siempre por encima de cejas y ojos."""
    r = CABEZA["r"] + extra
    th = math.degrees(math.asin(max(-1.0, y_corte / r)))   # ángulo (negativo) del corte
    a0, a1 = 180 - th, 360 + th
    caja = (hx - r, hy - r, hx + r, hy + r)
    L.cuerda(*caja, a0, a1, NEGRO)
    L.arco(*caja, a0, a1, c, 3.6)
    return a0, a1


def acc_cabello_coleta(L, esq, c):
    hx, hy = esq.cabeza
    r = CABEZA["r"]
    _casquete(L, hx, hy, c, extra=4)
    # melena: solo trazos por fuera del contorno de la cabeza (no tocan la cara)
    L.arco(hx - r - 5, hy - r - 5, hx + r + 5, hy + r + 5, 150, 250, c, 3.4)
    L.linea([(hx - 42, hy - 46), (hx - 22, hy - 56), (hx, hy - 58), (hx + 24, hy - 56), (hx + 42, hy - 46)], c, 3.0)
    # coleta
    L.linea([(hx + r - 2, hy - 30), (hx + r + 22, hy - 20), (hx + r + 30, hy + 10), (hx + r + 16, hy + 40)], c, 3.6)
    L.linea([(hx + r - 2, hy - 18), (hx + r + 14, hy - 4), (hx + r + 18, hy + 22), (hx + r + 16, hy + 40)], c, 3.6)


def acc_sombrero_paja(L, esq, c):
    hx, hy = esq.cabeza
    y = hy + Y_TOCADO - 10
    L.poli([(hx - 42, y - 4), (hx - 34, y - 52), (hx + 34, y - 52), (hx + 42, y - 4)], fill=NEGRO, outline=c, ancho=3.4)
    L.linea([(hx - 40, y - 16), (hx + 40, y - 16)], c, 5)
    L.elipse(hx, y, 92, 13, fill=NEGRO, outline=c, ancho=3.6)
    for k in range(-70, 80, 22):
        L.linea([(hx + k, y - 6), (hx + k + 8, y + 6)], c, 1.6)


def acc_bigote(L, esq, c):
    hx, hy = esq.cabeza
    y = hy + BOCA["dy"] - 13
    for s in (-1, 1):
        L.d.chord(L.caja(hx, y - 6, hx + s * 24, y + 8), 0, 360, fill=BLANCO)
        L.circulo(hx + s * 24, y - 2, 3.5, fill=BLANCO)


def acc_overol(L, esq, c):
    t = esq.torso()
    (x0, y0), (x1, _), (x2, y2), (x3, _) = t
    L.poli([(-17, y0 + 38), (17, y0 + 38), (19, y2), (-19, y2)], fill=None, outline=c, ancho=3)
    for s in (-1, 1):
        L.linea([(s * 14, y0 + 38), (s * 20, y0 + 2)], c, 3)
        L.circulo(s * 12, y0 + 44, 2.6, fill=c)
    L.d.rectangle(L.caja(-8, y0 + 52, 8, y0 + 64), outline=c, width=L.w(2))


def acc_horquilla(L, esq, c):
    mx, my = _mano(esq, "L")
    L.tubo([(mx, min(my + 120, 10)), (mx, my - 108)], 5, c)
    L.tubo([(mx - 20, my - 108), (mx + 20, my - 108)], 5, c)
    for k in (-20, 0, 20):
        L.tubo([(mx + k, my - 108), (mx + k, my - 150)], 4.4, c)


def acc_traje(L, esq, c):
    (xl, y0), (xr, _), _, (_, y2) = esq.torso()
    L.poli([(-11, y0 + 1), (11, y0 + 1), (0, y0 + 30)], fill=BLANCO)
    L.poli([(-4, y0 + 8), (4, y0 + 8), (6, y0 + 50), (0, y0 + 60), (-6, y0 + 50)], fill=c)
    for s in (-1, 1):
        L.linea([(s * 12, y0 + 1), (s * 4, y0 + 40), (s * 16, y0 + 30)], c, 3)
    L.circulo(0, y0 + 68, 2.4, fill=c)
    L.circulo(0, y0 + 80, 2.4, fill=c)


def acc_chistera(L, esq, c):
    hx, hy = esq.cabeza
    y = hy + Y_TOCADO - 8
    L.poli([(hx - 36, y), (hx - 32, y - 78), (hx + 32, y - 78), (hx + 36, y)], fill=NEGRO, outline=c, ancho=3.6)
    L.d.rectangle(L.caja(hx - 35, y - 20, hx + 35, y - 8), fill=c)
    L.elipse(hx, y, 60, 9, fill=NEGRO, outline=c, ancho=3.6)


def acc_monoculo(L, esq, c):
    hx, hy = esq.cabeza
    ex, ey = hx + OJO["dx"], hy + OJO["dy"]
    oro = (255, 214, 60)
    L.elipse(ex, ey, OJO["rx"] + 3.5, OJO["ry"] + 3.5, outline=oro, ancho=2.6)
    L.linea([(ex + OJO["rx"] + 3, ey + 6), (ex + 32, ey + 40), (ex + 18, ey + 80)], oro, 1.6)


def acc_casa_pecho(L, esq, c):
    _, y0 = esq.torso()[0]
    y = y0 + 44
    L.poli([(-14, y), (0, y - 13), (14, y)], outline=c, ancho=2.6)
    L.d.rectangle(L.caja(-10, y, 10, y + 14), outline=c, width=L.w(2.6))


def acc_gorra(L, esq, c):
    hx, hy = esq.cabeza
    r = CABEZA["r"] + 2
    _casquete(L, hx, hy, c, extra=2)
    yb = hy + Y_TOCADO
    w = math.sqrt(r * r - Y_TOCADO ** 2)
    L.linea([(hx - w, yb), (hx + w, yb)], c, 3.4)
    L.poli([(hx + 14, yb - 2), (hx + 88, yb - 8), (hx + 84, yb + 3), (hx + 14, yb + 2)], fill=NEGRO, outline=c, ancho=3.0)
    L.circulo(hx, hy - r, 4, fill=c)
    L.linea([(hx, hy - r), (hx - 14, yb - 2)], c, 1.8)
    L.linea([(hx, hy - r), (hx + 16, yb - 2)], c, 1.8)


def acc_calculadora(L, esq, c):
    mx, my = _mano(esq, "L")
    x0, y0 = mx - 20, my - 46
    L.d.rounded_rectangle(L.caja(x0, y0, x0 + 40, y0 + 52), radius=L.w(4), fill=NEGRO, outline=c, width=L.w(3))
    L.d.rectangle(L.caja(x0 + 6, y0 + 6, x0 + 34, y0 + 15), outline=c, width=L.w(2))
    for i in range(3):
        for j in range(3):
            L.d.rectangle(L.caja(x0 + 7 + i * 10, y0 + 21 + j * 9, x0 + 13 + i * 10, y0 + 26 + j * 9), fill=c)


def acc_llave(L, esq, c):
    mx, my = _mano(esq, "L")
    L.circulo(mx, my - 34, 12, outline=c, ancho=3.2)
    L.circulo(mx, my - 34, 4, outline=c, ancho=2)
    L.linea([(mx, my - 22), (mx, my + 18)], c, 3.4)
    L.linea([(mx, my + 8), (mx + 9, my + 8)], c, 3)
    L.linea([(mx, my + 16), (mx + 7, my + 16)], c, 3)


def _casita(L, x, y, s, c):
    L.poli([(x - 26 * s, y - 30 * s), (x, y - 54 * s), (x + 26 * s, y - 30 * s)], fill=NEGRO, outline=c, ancho=3)
    L.d.rectangle(L.caja(x - 20 * s, y - 30 * s, x + 20 * s, y), fill=NEGRO, outline=c, width=L.w(3))
    L.d.rectangle(L.caja(x - 6 * s, y - 16 * s, x + 6 * s, y), outline=c, width=L.w(2.4))
    L.d.rectangle(L.caja(x - 16 * s, y - 25 * s, x - 9 * s, y - 18 * s), outline=c, width=L.w(1.8))


def acc_casa_mano(L, esq, c):
    mx, my = _mano(esq, "R")
    _casita(L, mx, my - 8, 1.0, c)


def acc_camisa(L, esq, c):
    _, y0 = esq.torso()[0]
    for s in (-1, 1):
        L.poli([(0, y0 + 2), (s * 15, y0 + 1), (s * 10, y0 + 16)], outline=c, ancho=2.4)
    L.linea([(0, y0 + 4), (0, y0 + 92)], c, 2)
    for k in (24, 44, 64):
        L.circulo(0, y0 + k, 2, fill=c)
    L.d.rectangle(L.caja(-18, y0 + 30, -7, y0 + 42), outline=c, width=L.w(2))


def acc_cartel_casa(L, esq, c):
    mx, my = _mano(esq, "R")
    _casita(L, mx, my - 8, 0.9, c)


def acc_capa(L, esq, c):
    (xl, y0), (xr, _), _, _ = esq.torso()
    L.poli([(xl - 2, y0 + 2), (xr + 2, y0 + 2), (xr + 34, y0 + 168), (xr - 10, y0 + 152), (xl - 40, y0 + 182)],
           fill=NEGRO, outline=c, ancho=3.4)


def acc_corona(L, esq, c):
    hx, hy = esq.cabeza
    y = hy - CABEZA["r"] + 6
    oro = (255, 196, 40)
    pts = [(hx - 32, y), (hx - 36, y - 38), (hx - 16, y - 18), (hx, y - 44), (hx + 16, y - 18), (hx + 36, y - 38), (hx + 32, y)]
    L.poli(pts, fill=NEGRO, outline=oro, ancho=3.4)
    for x, yy in ((-36, -38), (0, -44), (36, -38)):
        L.circulo(hx + x, y + yy - 3, 3.5, fill=oro)


def acc_gafas(L, esq, c):
    hx, hy = esq.cabeza
    for s in (-1, 1):
        L.elipse(hx + s * OJO["dx"], hy + OJO["dy"], OJO["rx"] + 3.5, OJO["ry"] + 3.5, outline=c, ancho=2.6)
    for s in (-1, 1):
        L.linea([(hx + s * (OJO["dx"] + OJO["rx"] + 3), hy + OJO["dy"] - 4), (hx + s * 58, hy - 2)], c, 2.4)


def acc_tableta(L, esq, c):
    mx, my = _mano(esq, "R")
    x0, y0 = mx - 8, my - 70
    L.d.rounded_rectangle(L.caja(x0, y0, x0 + 56, y0 + 76), radius=L.w(5), fill=NEGRO, outline=c, width=L.w(3))
    for i, h in enumerate((14, 24, 34, 46)):
        L.d.rectangle(L.caja(x0 + 9 + i * 11, y0 + 64 - h, x0 + 16 + i * 11, y0 + 64), fill=c)
    L.linea([(x0 + 8, y0 + 40), (x0 + 24, y0 + 30), (x0 + 34, y0 + 34), (x0 + 50, y0 + 14)], c, 2)


def acc_credencial(L, esq, c):
    _, y0 = esq.torso()[0]
    L.linea([(-10, y0 - 2), (0, y0 + 40), (10, y0 - 2)], c, 1.8)
    L.d.rectangle(L.caja(-9, y0 + 40, 9, y0 + 62), fill=NEGRO, outline=c, width=L.w(2.4))
    L.linea([(-5, y0 + 54), (5, y0 + 54)], c, 1.6)


ACCESORIOS = {
    "mechon": ("cabeza", acc_mechon), "cabello_coleta": ("cabeza", acc_cabello_coleta),
    "sombrero_paja": ("cabeza", acc_sombrero_paja), "bigote": ("cabeza", acc_bigote),
    "overol": ("cuerpo", acc_overol), "horquilla": ("objeto", acc_horquilla),
    "traje": ("cuerpo", acc_traje), "chistera": ("cabeza", acc_chistera), "monoculo": ("cabeza", acc_monoculo),
    "casa_pecho": ("cuerpo", acc_casa_pecho), "gorra": ("cabeza", acc_gorra),
    "calculadora": ("objeto", acc_calculadora), "llave": ("objeto", acc_llave),
    "casa_mano": ("objeto", acc_casa_mano), "camisa": ("cuerpo", acc_camisa),
    "cartel_casa": ("objeto", acc_cartel_casa), "capa": ("detras", acc_capa),
    "corona": ("cabeza", acc_corona), "gafas": ("cabeza", acc_gafas),
    "tableta": ("objeto", acc_tableta), "credencial": ("cuerpo", acc_credencial),
}


# ───────────────────────── cuerpo ─────────────────────────
def _trazos_brazo(b):
    trazos = [([b["hombro"], b["codo"], b["mano"]], TUBO)]
    mx, my = b["mano"]
    fx, fy = b["mano"][0] - b["codo"][0], b["mano"][1] - b["codo"][1]
    n = math.hypot(fx, fy) or 1
    fx, fy = fx / n, fy / n
    if b["tipo"] == "senalar":
        dx, dy = b["dir"] or (fx, fy)
        trazos.append(([(mx, my), (mx + dx * 19, my + dy * 19)], 8.5))
    elif b["tipo"] == "pulgar":
        trazos.append(([(mx, my), (mx, my - 17)], 8.5))
    elif b["tipo"] == "abierta":
        # pulgar abierto, perpendicular al antebrazo, hacia arriba
        px, py = -fy * b["lado"], fx * b["lado"]
        if py > 0:
            px, py = -px, -py
        trazos.append(([(mx, my), (mx + px * 13 + fx * 4, my + py * 13 + fy * 4)], 8.0))
        trazos.append(([(mx, my), (mx + fx * 12, my + fy * 12)], 10.5))
    return trazos


def _contorno(L, trazos, color, circulos=()):
    for pts, w in trazos:
        L.tubo(pts, w, color)
    for x, y, r in circulos:
        L.circulo(x, y, r, fill=color)
    for pts, w in trazos:
        L.tubo(pts, w - 2 * BORDE, NEGRO)
    for x, y, r in circulos:
        L.circulo(x, y, r - BORDE, fill=NEGRO)


def _cuerpo(L, esq, color):
    t = esq.torso()
    trazos = [([p["cadera"], p["rodilla"], p["pie"]], TUBO) for p in esq.piernas.values()]
    trazos += [([p["pie"], (p["pie"][0] + p["lado"] * 12, p["pie"][1] + 1)], TUBO) for p in esq.piernas.values()]
    trazos.append(([(0, esq.cabeza[1] + 40), (0, t[0][1] + 6)], TUBO))
    for pts, w in trazos:
        L.tubo(pts, w, color)
    L.poli(t, fill=color)
    L.d.rounded_rectangle(L.caja(t[0][0], t[0][1], t[1][0], t[0][1] + 16), radius=L.w(8), fill=color)
    for pts, w in trazos:
        L.tubo(pts, w - 2 * BORDE, NEGRO)
    b = BORDE
    L.poli([(t[0][0] + b * 1.1, t[0][1] + b), (t[1][0] - b * 1.1, t[1][1] + b),
            (t[2][0] - b * 1.1, t[2][1] - b), (t[3][0] + b * 1.1, t[3][1] - b)], fill=NEGRO)
    L.d.rounded_rectangle(L.caja(t[0][0] + b, t[0][1] + b, t[1][0] - b, t[0][1] + 16), radius=L.w(6), fill=NEGRO)


def _brazo(L, b, color):
    _contorno(L, _trazos_brazo(b), color, [(b["mano"][0], b["mano"][1], MANO)])


def _cabeza(L, esq, color):
    hx, hy = esq.cabeza
    L.circulo(hx, hy, CABEZA["r"], fill=NEGRO, outline=color, ancho=CABEZA["borde"])


# ───────────────────────── render ─────────────────────────
def dibujar_personaje(L: Lienzo, clave: str, expresion: str = "neutral", pose: str | None = None,
                      dy_cuerpo: float = 0.0, accesorios: bool = True, boca: str | None = None,
                      color: tuple | None = None):
    p = catalogo()[clave]
    pose = pose or p["pose"]
    c = color or p["rgb"]
    esq = Esqueleto(pose, dy_cuerpo)
    accs = [ACCESORIOS[a] for a in p["accesorios"]] if accesorios else []

    def capa(nombre):
        for cp, fn in accs:
            if cp == nombre:
                fn(L, esq, c)

    capa("detras")
    _cuerpo(L, esq, c)
    capa("cuerpo")
    capa("objeto")
    atras = "L" if esq.delante == "R" else "R"
    _brazo(L, esq.brazos[atras], c)
    _brazo(L, esq.brazos[esq.delante], c)
    _cabeza(L, esq, c)
    # `boca` permite la sincronía labial: cambia solo la boca, la cara sigue siendo la maestra
    dibujar_cara(L, *esq.cabeza, expresion, boca)
    capa("cabeza")
    return esq


def render(clave: str, expresion: str | None = None, pose: str | None = None, alto: int = 600,
           brillo: bool = True, espejo: bool = False, dy_cuerpo: float = 0.0,
           accesorios: bool = True, boca: str | None = None, color: tuple | None = None) -> Image.Image:
    """Sprite RGBA del personaje. `alto` = altura en px de la figura (pies → coronilla).

    El ancla (suelo, centro) está en (ancho/2, alto_img - ABAJO*escala).
    """
    p = catalogo()[clave]
    expresion = expresion or p.get("expresion", "neutral")
    s = alto / ALTURA_FIGURA
    W, H = int(2 * LX * s), int((ARRIBA + ABAJO) * s)
    img = Image.new("RGBA", (W * SS, H * SS), (0, 0, 0, 0))
    L = Lienzo(ImageDraw.Draw(img), s * SS, LX * s * SS, ARRIBA * s * SS)
    dibujar_personaje(L, clave, expresion, pose, dy_cuerpo, accesorios, boca, color)
    img = img.resize((W, H), Image.LANCZOS)
    if brillo:
        img = con_brillo(img, radio=max(2, alto / 90))
    if espejo:
        img = img.transpose(Image.FLIP_LEFT_RIGHT)
    return img


def con_brillo(img: Image.Image, radio: float = 6) -> Image.Image:
    """Halo neón: difumina la propia imagen y la coloca debajo."""
    halo = img.filter(ImageFilter.GaussianBlur(radio))
    base = Image.new("RGBA", img.size, (0, 0, 0, 0))
    base.alpha_composite(halo)
    base.alpha_composite(halo)
    base.alpha_composite(img)
    return base


def ancla(alto: int) -> tuple[float, float]:
    s = alto / ALTURA_FIGURA
    return LX * s, ARRIBA * s


def caja_cabeza(alto: int, margen: float = 1.35, dy_cuerpo: float = 0.0) -> tuple[int, int, int, int]:
    """Recuadro (px) de la cabeza dentro del sprite, para primeros planos."""
    s = alto / ALTURA_FIGURA
    ax, ay = ancla(alto)
    r = CABEZA["r"] * margen
    cy = CABEZA["cy"] + dy_cuerpo
    arriba = CABEZA["r"] * 2.4   # deja sitio a chistera, corona y sombrero
    return (int(ax - r * s), int(ay + (cy - max(r * 1.15, arriba)) * s), int(ax + r * s), int(ay + (cy + r) * s))


def mascara_cara(expresion: str, alto: int) -> Image.Image:
    """Máscara (L) de los rasgos faciales: sirve a los tests de consistencia."""
    s = alto / ALTURA_FIGURA
    W, H = int(2 * LX * s), int((ARRIBA + ABAJO) * s)
    img = Image.new("RGBA", (W * SS, H * SS), (0, 0, 0, 0))
    L = Lienzo(ImageDraw.Draw(img), s * SS, LX * s * SS, ARRIBA * s * SS)
    dibujar_cara(L, CABEZA["cx"], CABEZA["cy"], expresion)
    return img.resize((W, H), Image.LANCZOS).getchannel("A")
