"""Hojas de personajes para aprobación visual.

    python -m pilo_studio.personajes.hoja [carpeta_salida]

Genera en personajes/hojas/:
  hoja_personajes.png   – los 13 personajes por marca, en su pose y expresión de firma
  hoja_expresiones.png  – 13 personajes × 12 expresiones (primer plano, misma cara maestra)
  hoja_poses.png        – las 8 poses oficiales con el narrador de cada marca
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from pilo_studio.personajes import rig

FONDO = (8, 8, 18, 255)
FUENTE = "/usr/share/fonts/opentype/inter/InterDisplay-ExtraBold.otf"
MARCAS = [("fact-stick", "FACT STICK"), ("money-lab", "MONEY LAB"), ("wild-money", "WILD MONEY")]
EXPR = list(rig.EXPRESIONES)
NARRADORES = ["blue", "cyan", "orange"]
ETIQUETA_POSE = {"explicando": "EXPLICANDO", "senalando": "SEÑALANDO", "pensando": "PENSANDO",
                 "presentando": "PRESENTANDO", "preguntando": "PREGUNTANDO", "brazos_cruzados": "BRAZOS CRUZADOS",
                 "pulgar_arriba": "PULGAR ARRIBA", "celebrando": "CELEBRANDO"}


def _f(n):
    try:
        return ImageFont.truetype(FUENTE, n)
    except OSError:
        return ImageFont.load_default()


def _texto(img, xy, txt, n, color=(240, 240, 255), anchor="mm"):
    ImageDraw.Draw(img).text(xy, txt, font=_f(n), fill=color, anchor=anchor)


def hoja_personajes() -> Image.Image:
    cw, alto = 380, 400
    ay = int(rig.ancla(alto)[1])
    ch = ay + 40
    img = Image.new("RGBA", (cw * 5 + 80, 140 + len(MARCAS) * (ch + 90)), FONDO)
    _texto(img, (img.width // 2, 70), "PILO STUDIO · 13 PERSONAJES · CARA MAESTRA ÚNICA", 52)
    y = 140
    for marca, titulo in MARCAS:
        _texto(img, (60, y + 30), titulo, 44, anchor="lm")
        for i, k in enumerate(rig.personajes_de(marca)):
            p = rig.catalogo()[k]
            sp = rig.render(k, alto=alto)
            x0 = 40 + i * cw
            img.alpha_composite(sp, (x0 + cw // 2 - sp.width // 2, y + 40))
            _texto(img, (x0 + cw // 2, y + 40 + ay + 30), p["nombre"].upper(), 36, p["rgb"])
        y += ch + 90
    return img


def hoja_expresiones() -> Image.Image:
    celda, alto = 170, 330
    img = Image.new("RGBA", (200 + celda * len(EXPR), 120 + celda * len(rig.catalogo())), FONDO)
    for j, e in enumerate(EXPR):
        _texto(img, (200 + j * celda + celda // 2, 90), e.capitalize(), 22)
    _texto(img, (img.width // 2, 36), "12 EXPRESIONES · MISMA CARA EN LOS 13 PERSONAJES", 40)
    caja = rig.caja_cabeza(alto, margen=1.55)
    for i, (k, p) in enumerate(rig.catalogo().items()):
        _texto(img, (20, 120 + i * celda + celda // 2), p["nombre"], 28, p["rgb"], anchor="lm")
        for j, e in enumerate(EXPR):
            cab = rig.render(k, expresion=e, pose="neutral", alto=alto).crop(caja)
            cab.thumbnail((celda - 8, celda - 8))
            img.alpha_composite(cab, (200 + j * celda + (celda - cab.width) // 2, 120 + i * celda + (celda - cab.height) // 2))
    return img


def hoja_poses() -> Image.Image:
    cw, alto = 300, 300
    ch = int(rig.ancla(alto)[1]) + 20
    poses = rig.POSES_OFICIALES
    img = Image.new("RGBA", (40 + cw * len(poses), 160 + len(NARRADORES) * ch), FONDO)
    _texto(img, (img.width // 2, 40), "8 POSES OFICIALES", 44)
    for j, po in enumerate(poses):
        _texto(img, (20 + j * cw + cw // 2, 110), ETIQUETA_POSE[po], 24)
    for i, k in enumerate(NARRADORES):
        for j, po in enumerate(poses):
            sp = rig.render(k, expresion="talking" if j % 2 else "happy", pose=po, alto=alto)
            img.alpha_composite(sp, (20 + j * cw + cw // 2 - sp.width // 2, 130 + i * ch))
    return img


def generar(salida: Path | None = None) -> list[Path]:
    salida = Path(salida or rig.RAIZ / "personajes" / "hojas")
    salida.mkdir(parents=True, exist_ok=True)
    rutas = []
    for nombre, fn in (("hoja_personajes", hoja_personajes), ("hoja_expresiones", hoja_expresiones),
                       ("hoja_poses", hoja_poses)):
        r = salida / f"{nombre}.png"
        fn().convert("RGB").save(r, optimize=True)
        rutas.append(r)
    return rutas


if __name__ == "__main__":
    for r in generar(Path(sys.argv[1]) if len(sys.argv) > 1 else None):
        print(r)
