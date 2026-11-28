"""Hojas de personajes para aprobación visual.

    python -m pilo_studio.personajes.hoja [carpeta_salida]

Genera en personajes/hojas/:
  hoja_personajes.png   – los 13 personajes por marca, en su pose y expresión de firma
  hoja_expresiones.png  – 13 personajes × 12 expresiones (primer plano, misma cara maestra)
  hoja_poses.png        – las 8 poses oficiales con el narrador de cada marca
  hoja_rostros.png      – los 13 rostros neutrales, zona facial protegida y superposición
  validacion_rostro.md  – medidas de ojos, pupilas, cejas y boca en los 13 (sobre el render)
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

import numpy as np

from pilo_studio.personajes import rig, validacion

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


def hoja_rostros() -> Image.Image:
    alto, celda = 520, 250
    claves = list(rig.catalogo())
    img = Image.new("RGBA", (40 + celda * 7, 200 + 2 * (celda + 60)), FONDO)
    _texto(img, (img.width // 2, 40), "ROSTRO MAESTRO · EXPRESIÓN NEUTRAL · 13 PERSONAJES", 40)
    _texto(img, (img.width // 2, 90), "Recuadro discontinuo = zona facial protegida (ningún accesorio entra)", 24, (170, 170, 200))
    caja = rig.caja_cabeza(alto, margen=1.55)
    zx0, zy0, zx1, zy1 = validacion.zona_px(alto)
    zonas = []
    for i, k in enumerate(claves + ["__superpuestos"]):
        x, y = 20 + (i % 7) * celda, 130 + (i // 7) * (celda + 60)
        if k == "__superpuestos":
            media = np.mean(zonas, axis=0).astype("uint8")
            cab = Image.fromarray(media).convert("RGBA")
            cab = cab.resize((int(cab.width * 1.6), int(cab.height * 1.6)), Image.LANCZOS)
            img.alpha_composite(cab, (x + (celda - cab.width) // 2, y + (celda - cab.height) // 2))
            _texto(img, (x + celda // 2, y + celda + 25), "13 SUPERPUESTOS", 22)
            continue
        sp = rig.render(k, expresion="neutral", pose="neutral", alto=alto)
        d = ImageDraw.Draw(sp)
        for t in range(0, zx1 - zx0, 14):   # recuadro discontinuo de la zona facial
            d.line([(zx0 + t, zy0), (min(zx0 + t + 7, zx1), zy0)], fill=(255, 255, 255, 160), width=2)
            d.line([(zx0 + t, zy1), (min(zx0 + t + 7, zx1), zy1)], fill=(255, 255, 255, 160), width=2)
        for t in range(0, zy1 - zy0, 14):
            d.line([(zx0, zy0 + t), (zx0, min(zy0 + t + 7, zy1))], fill=(255, 255, 255, 160), width=2)
            d.line([(zx1, zy0 + t), (zx1, min(zy0 + t + 7, zy1))], fill=(255, 255, 255, 160), width=2)
        cab = sp.crop(caja)
        cab.thumbnail((celda - 10, celda - 10))
        img.alpha_composite(cab, (x + (celda - cab.width) // 2, y + (celda - cab.height) // 2))
        p = rig.catalogo()[k]
        _texto(img, (x + celda // 2, y + celda + 25), p["nombre"].upper(), 26, p["rgb"])
        zonas.append(validacion.zona(k, "neutral", alto).clip(0, 255))
    return img


def generar(salida: Path | None = None) -> list[Path]:
    salida = Path(salida or rig.RAIZ / "personajes" / "hojas")
    salida.mkdir(parents=True, exist_ok=True)
    rutas = []
    for nombre, fn in (("hoja_personajes", hoja_personajes), ("hoja_expresiones", hoja_expresiones),
                       ("hoja_poses", hoja_poses), ("hoja_rostros", hoja_rostros)):
        r = salida / f"{nombre}.png"
        fn().convert("RGB").save(r, optimize=True)
        rutas.append(r)
    ok, texto = validacion.informe()
    r = salida / "validacion_rostro.md"
    r.write_text(texto, encoding="utf-8")
    rutas.append(r)
    print("Validación del rostro:", "APROBADO" if ok else "FALLA")
    return rutas


if __name__ == "__main__":
    for r in generar(Path(sys.argv[1]) if len(sys.argv) > 1 else None):
        print(r)
