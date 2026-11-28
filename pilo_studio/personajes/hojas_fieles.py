"""Hojas visuales de los 13 personajes fieles (lote).

    python -m pilo_studio.personajes.hojas_fieles

Genera en personajes/hojas_fieles/:
  hoja_personajes.png   – los 13 en la pose de su guía, por marca
  hoja_expresiones.png  – 13 × 12 expresiones (rostro maestro sobre la cabeza trazada)
  hoja_poses.png        – 13 × 8 poses oficiales
  hoja_rostros.png      – el rostro maestro normalizado de los 13 (prueba visual de identidad)
"""
from __future__ import annotations

from PIL import Image, ImageDraw, ImageFont

from pilo_studio.personajes import articulado, fiel, lote

SALIDA = fiel.RAIZ / "personajes" / "hojas_fieles"
FUENTE = "/usr/share/fonts/opentype/inter/InterDisplay-ExtraBold.otf"
FONDO = (8, 8, 18)
MARCAS = [("fact-stick", "FACT STICK"), ("money-lab", "MONEY LAB"), ("wild-money", "WILD MONEY")]
NOMBRES = {k: k.upper() for k in lote.PERSONAJES}


def _f(n):
    return ImageFont.truetype(FUENTE, n)


def _encajar(im: Image.Image, w: int, h: int) -> Image.Image:
    im = im.copy()
    im.thumbnail((w, h), Image.LANCZOS)
    return im


def hoja_personajes() -> Image.Image:
    cw, ch = 420, 470
    img = Image.new("RGB", (40 + 5 * cw, 120 + 3 * (ch + 80)), FONDO)
    d = ImageDraw.Draw(img)
    d.text((img.width // 2, 55), "PILO STUDIO · 13 PERSONAJES FIELES A SUS GUÍAS · ROSTRO MAESTRO COMÚN",
           font=_f(40), fill=(240, 240, 255), anchor="mm")
    y = 110
    for marca, titulo in MARCAS:
        d.text((30, y + 20), titulo, font=_f(36), fill=(240, 240, 255), anchor="lm")
        for i, k in enumerate([c for c, (m, _) in lote.PERSONAJES.items() if m == marca]):
            im = _encajar(fiel.render_capas(k, k=3), cw - 20, ch - 60)
            x = 20 + i * cw
            img.paste(im, (x + (cw - im.width) // 2, y + 50))
            color = tuple(max(fiel.cargar(k)["capas"], key=lambda c: len(c["polis"]))["color"])
            d.text((x + cw // 2, y + 50 + ch - 30), NOMBRES[k], font=_f(30), fill=color, anchor="mm")
        y += ch + 80
    return img


def _cabeza(k: str, expresion: str, lado: int) -> Image.Image:
    dd = fiel.cargar(k)
    esc = 4
    im = fiel.render_capas(dd, k=esc, expresion=expresion)
    (mx, my), s = dd["rostro"]["medio"], dd["rostro"]["escala"]
    cx, cy = (mx - 0.25 * s) * esc, (my - 0.25 * s) * esc
    r = 1.85 * s * esc
    return im.crop((int(cx - r), int(cy - r), int(cx + r), int(cy + r))).resize((lado, lado), Image.LANCZOS)


def hoja_expresiones() -> Image.Image:
    lado = 150
    claves = list(lote.PERSONAJES)
    img = Image.new("RGB", (190 + lado * 12, 110 + lado * len(claves)), FONDO)
    d = ImageDraw.Draw(img)
    d.text((img.width // 2, 35), "12 EXPRESIONES · MISMO ROSTRO MAESTRO EN LOS 13", font=_f(36), fill=(240, 240, 255), anchor="mm")
    for j, e in enumerate(fiel.EXPRESIONES):
        d.text((190 + j * lado + lado // 2, 88), e.capitalize(), font=_f(20), fill=(220, 220, 235), anchor="mm")
    for i, k in enumerate(claves):
        d.text((15, 110 + i * lado + lado // 2), NOMBRES[k], font=_f(24), fill=(220, 220, 235), anchor="lm")
        for j, e in enumerate(fiel.EXPRESIONES):
            img.paste(_cabeza(k, e, lado - 6), (190 + j * lado + 3, 110 + i * lado + 3))
    return img


def hoja_poses() -> Image.Image:
    cw, ch = 210, 250
    claves = list(lote.PERSONAJES)
    img = Image.new("RGB", (170 + cw * 8, 110 + ch * len(claves)), FONDO)
    d = ImageDraw.Draw(img)
    d.text((img.width // 2, 35), "8 POSES OFICIALES · 13 PERSONAJES", font=_f(36), fill=(240, 240, 255), anchor="mm")
    for j, p in enumerate(articulado.POSES):
        d.text((170 + j * cw + cw // 2, 88), articulado.ETIQUETAS[p], font=_f(18), fill=(220, 220, 235), anchor="mm")
    for i, k in enumerate(claves):
        d.text((15, 110 + i * ch + ch // 2), NOMBRES[k], font=_f(24), fill=(220, 220, 235), anchor="lm")
        for j, p in enumerate(articulado.POSES):
            im = _encajar(articulado.render_pose(k, p, expresion="talking" if j % 2 else "happy", k=2), cw - 8, ch - 8)
            img.paste(im, (170 + j * cw + (cw - im.width) // 2, 110 + i * ch + (ch - im.height) // 2))
    return img


def hoja_rostros() -> Image.Image:
    from pilo_studio.personajes import validar
    lado = 200
    claves = list(lote.PERSONAJES)
    img = Image.new("RGB", (40 + 7 * (lado + 20), 140 + 2 * (lado + 60)), FONDO)
    d = ImageDraw.Draw(img)
    d.text((img.width // 2, 40), "ROSTRO MAESTRO NORMALIZADO (mismo centro y escala) · idéntico en los 13",
           font=_f(30), fill=(240, 240, 255), anchor="mm")
    for i, k in enumerate(claves):
        m = validar.rostro_normalizado(k)
        im = Image.fromarray((m * 255).astype("uint8")).convert("RGB")
        x, y = 20 + (i % 7) * (lado + 20), 90 + (i // 7) * (lado + 60)
        img.paste(im, (x, y))
        d.text((x + lado // 2, y + lado + 22), NOMBRES[k], font=_f(24), fill=(220, 220, 235), anchor="mm")
    return img


def generar():
    SALIDA.mkdir(parents=True, exist_ok=True)
    rutas = []
    for n, fn in (("hoja_personajes", hoja_personajes), ("hoja_expresiones", hoja_expresiones),
                  ("hoja_poses", hoja_poses), ("hoja_rostros", hoja_rostros)):
        r = SALIDA / f"{n}.png"
        fn().save(r, optimize=True)
        rutas.append(r)
        print(r)
    return rutas


if __name__ == "__main__":
    generar()
