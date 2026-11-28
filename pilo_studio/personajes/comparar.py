"""Hoja de comparación de fidelidad con la guía oficial.

    python -m pilo_studio.personajes.comparar blue

Paneles: referencia original | reconstrucción | superposición 50 % | mapa de diferencias
(rojo = solo guía, verde = solo reconstrucción, amarillo = coinciden). Debajo, la medida
de coincidencia del trazo y la lista de diferencias que quedan.
"""
from __future__ import annotations

import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from pilo_studio.personajes import fiel

FUENTE = "/usr/share/fonts/opentype/inter/InterDisplay-ExtraBold.otf"
FUENTE_TXT = "/usr/share/fonts/opentype/inter/Inter-SemiBold.otf"
K = 4
ALTO_UTIL = 215          # la guía corta el retrato aquí (debajo está el texto de la tarjeta)
ZONA = (20, 6, 205, 200)  # zona medida: excluye el marco de la tarjeta

DIFERENCIAS = {
    "blue": [
        "Corregido respecto al rig anterior: cabeza ovalada 100×92 px unida al cuello sin línea de cierre;",
        "  mechón de dos puntas cerradas; ojos de distinto tamaño (perspectiva) con pupila apoyada en el borde;",
        "  boca con banda blanca curva y lengua roja; silueta única con brazos gruesos; puño en la cadera;",
        "  mano abierta tipo manopla con pulgar y líneas de dedos; trazo de 3,8 px con halo.",
        "Diferencias que quedan (≤ 2 px salvo indicación):",
        "  1. Segunda punta del mechón: el borde inferior difiere unos 2 px.",
        "  2. Puño en la cadera: la guía dibuja nudillos; aquí es un óvalo liso.",
        "  3. Lengua: forma inclinada aproximada con 8 puntos; el borde de la guía es más irregular.",
        "  4. Neón: la guía varía el grosor del trazo; aquí es uniforme.",
        "  5. Piernas: la guía corta a Blue en la cadera; las piernas completas no están definidas en la guía.",
    ],
}


def _trazo(img: np.ndarray) -> np.ndarray:
    return (img[..., 1] > 160) & (img[..., 2] > 200) & (img[..., 0] < 150)


def _dil(m, px):
    return np.array(Image.fromarray((m * 255).astype("uint8")).filter(ImageFilter.MaxFilter(2 * px + 1))) > 0


def medir(clave: str) -> dict:
    archivo, (x0, y0, x1, _) = fiel.REFERENCIAS[clave]
    g = np.array(Image.open(fiel.RAIZ / archivo).convert("RGB").crop((x0, y0, x1, y0 + ALTO_UTIL))).astype(int)
    r = np.array(fiel.render(getattr(fiel, clave.upper()), k=1, caja=(0, 0, x1 - x0, ALTO_UTIL), brillo=False)).astype(int)
    zona = np.zeros(g.shape[:2], bool)
    zona[ZONA[1]:ZONA[3], ZONA[0]:ZONA[2]] = True
    ref, rec = _trazo(g) & zona, _trazo(r) & zona
    res = {"ref": ref, "rec": rec, "g": g, "r": r}
    for tol in (1, 2):
        res[f"guia_{tol}"] = (ref & _dil(rec, tol)).sum() / ref.sum()
        res[f"propio_{tol}"] = (rec & _dil(ref, tol)).sum() / rec.sum()
    return res


def comparar(clave: str) -> Image.Image:
    archivo, (x0, y0, x1, _) = fiel.REFERENCIAS[clave]
    ref = Image.open(fiel.RAIZ / archivo).convert("RGB").crop((x0, y0, x1, y0 + ALTO_UTIL))
    ref = ref.resize((ref.width * K, ref.height * K), Image.LANCZOS)
    rec = fiel.render(getattr(fiel, clave.upper()), k=K, caja=(0, 0, x1 - x0, ALTO_UTIL))
    sup = Image.blend(ref, rec, 0.5)
    m = medir(clave)
    dif = np.zeros(m["g"].shape, "uint8")
    dif[m["ref"]] = (255, 40, 40)
    dif[m["rec"]] = (40, 255, 40)
    dif[m["ref"] & m["rec"]] = (255, 230, 0)
    dif = Image.fromarray(dif).resize(ref.size, Image.NEAREST)

    W, H = ref.size
    lineas = DIFERENCIAS.get(clave, [])
    img = Image.new("RGB", (W * 4 + 100, H + 230 + 40 * len(lineas)), (8, 8, 18))
    d = ImageDraw.Draw(img)
    f, ft = ImageFont.truetype(FUENTE, 32), ImageFont.truetype(FUENTE_TXT, 28)
    titulos = ("REFERENCIA ORIGINAL (guía)", "RECONSTRUCCIÓN (código)", "SUPERPOSICIÓN 50 %",
               "DIFERENCIAS: rojo guía · verde código")
    for i, (im, t) in enumerate(zip((ref, rec, sup, dif), titulos)):
        x = 20 + i * (W + 20)
        img.paste(im, (x, 100))
        d.text((x + W // 2, 55), t, font=f, fill=(240, 240, 255), anchor="mm")
    y = H + 130
    d.text((20, y), f"{clave.upper()} · coincidencia del trazo neón con la guía: "
                    f"{m['guia_2']:.0%} con tolerancia de 2 px ({m['guia_1']:.0%} con 1 px)",
           font=f, fill=(255, 230, 0))
    for i, t in enumerate(lineas):
        d.text((20, y + 60 + i * 40), t, font=ft, fill=(220, 220, 235))
    return img


if __name__ == "__main__":
    clave = sys.argv[1] if len(sys.argv) > 1 else "blue"
    salida = fiel.RAIZ / "personajes" / "comparaciones"
    salida.mkdir(parents=True, exist_ok=True)
    ruta = salida / f"{clave}_comparacion.png"
    comparar(clave).save(ruta, optimize=True)
    print(ruta)
