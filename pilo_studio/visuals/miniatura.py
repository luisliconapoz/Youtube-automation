"""Miniatura (thumbnail) automática lista para subir.

El fondo se genera en el mismo lote que las escenas; aquí se compone el
texto grande con contorno, al estilo de las miniaturas de YouTube.
Largo: 1280×720 JPG (< 2 MB, requisito de YouTube). Short: portada 1080×1920.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

from pilo_studio.models import Guion
from pilo_studio.utils import log
from pilo_studio.visuals.estilo import BibliaEstilo

FUENTES = ["DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "Arial Bold.ttf", "arialbd.ttf"]


def tam_miniatura(formato: str) -> tuple[int, int]:
    return (1080, 1920) if formato == "short" else (1280, 720)


def prompt_miniatura(guion: Guion, biblia: BibliaEstilo) -> str:
    base = guion.miniatura_prompt or (
        f"{guion.titulo}, eye-catching YouTube thumbnail, close-up of the main subject with an intense emotion, "
        "dramatic rim lighting, high contrast, simple composition, empty space for a headline")
    partes = [biblia.estilo.descripcion, base]
    presentes = {p for e in guion.escenas for p in e.personajes}
    for nombre, desc in biblia.estilo.personajes.items():
        if nombre in presentes or nombre.lower() in base.lower():
            partes.append(f"{nombre}: {desc}")
    if biblia.paleta:
        partes.append(f"color palette {' '.join(biblia.paleta)}")
    partes.append("no text, no letters, no watermark")
    return ", ".join(p.strip().rstrip(".") for p in partes if p)


def _fuente(tam: int) -> ImageFont.FreeTypeFont:
    for f in FUENTES:
        try:
            return ImageFont.truetype(f, tam)
        except OSError:
            continue
    return ImageFont.load_default(size=tam)


def _envolver(texto: str, fuente, ancho_max: int, draw: ImageDraw.ImageDraw) -> list[str]:
    lineas, actual = [], ""
    for palabra in texto.split():
        prueba = f"{actual} {palabra}".strip()
        if actual and draw.textlength(prueba, font=fuente) > ancho_max:
            lineas.append(actual)
            actual = palabra
        else:
            actual = prueba
    return lineas + ([actual] if actual else [])


def componer_miniatura(fondo: Path, texto: str, formato: str, salida: Path) -> Path:
    ancho, alto = tam_miniatura(formato)
    img = ImageOps.fit(Image.open(fondo).convert("RGB"), (ancho, alto), Image.Resampling.LANCZOS)
    texto = (texto or "").strip().upper()
    if texto:
        # Degradado oscuro en la parte inferior para que el texto destaque
        sombra = Image.new("L", (1, alto))
        for y in range(alto):
            sombra.putpixel((0, y), int(200 * max(0.0, (y / alto - 0.45) / 0.55)))
        negro = Image.new("RGB", (ancho, alto), (0, 0, 0))
        img = Image.composite(negro, img, sombra.resize((ancho, alto)))

        d = ImageDraw.Draw(img)
        margen = int(ancho * 0.06)
        tam = int(alto * (0.11 if formato == "short" else 0.17))
        while True:  # reducir hasta que quepa en ≤3 líneas
            fuente = _fuente(tam)
            lineas = _envolver(texto, fuente, ancho - 2 * margen, d)
            if len(lineas) <= 3 or tam < 30:
                break
            tam = int(tam * 0.88)
        alto_linea = int(tam * 1.12)
        y = alto - margen - alto_linea * len(lineas) - (int(alto * 0.12) if formato == "short" else 0)
        colores = ["#FFFFFF", "#FFD60A"]  # alterna blanco / amarillo
        for i, linea in enumerate(lineas):
            d.text((margen, y + i * alto_linea), linea, font=fuente, fill=colores[i % 2],
                   stroke_width=max(4, tam // 12), stroke_fill="black")
    salida.parent.mkdir(parents=True, exist_ok=True)
    calidad = 92
    while True:
        img.save(salida, "JPEG", quality=calidad, optimize=True)
        if salida.stat().st_size < 2_000_000 or calidad <= 60:
            break
        calidad -= 8
    log.info("  🖼  Miniatura lista: %s", salida.name)
    return salida
