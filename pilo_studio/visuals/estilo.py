"""Biblia de estilo y dirección de arte: consistencia visual y reglas estrictas.

Cada prompt de imagen se construye SIEMPRE con la misma estructura:

    [estilo neón 2D] + [escena] + [personajes oficiales: rol, colores, aspecto,
    expresión, pose] + [escenario] + [paleta] + [encuadre] + [prohibiciones]

y se limpia de cualquier texto o número que pudiera acabar dibujado en la imagen.
"""

from __future__ import annotations

import re
from pathlib import Path

from PIL import Image

from pilo_studio.models import Escena
from pilo_studio.proyecto import Proyecto
from pilo_studio.utils import semilla

# Valores por defecto: se pueden ajustar en settings.yaml -> direccion_arte
ESTILO_NEON = ("simple minimalist 2D neon vector illustration on a pure black background, stick-figure characters "
               "with solid black round heads, big white cartoon eyes and thin glowing neon outline bodies, "
               "clean glowing lines, flat shapes, one clear idea, uncluttered, crisp professional look")
# Listas oficiales de las guías (EXPRESSIONS / COMMON POSES)
EXPRESIONES = ["Neutral", "Happy", "Talking", "Surprised", "Confused", "Thinking", "Concerned", "Skeptical",
               "Excited", "Angry", "Serious", "Smug"]
POSES = ["Explaining", "Pointing", "Thinking", "Presenting", "Questioning", "Arms crossed", "Thumbs up",
         "Celebrating"]
# Cómo se dibuja cada pose oficial
POSES_DESCRIPCION = {
    "Explaining": "explaining with one open hand extended to the side",
    "Pointing": "pointing with an outstretched arm",
    "Thinking": "hand on chin, thinking",
    "Presenting": "presenting with both arms open",
    "Questioning": "shrugging with a question gesture",
    "Arms crossed": "standing with arms crossed",
    "Thumbs up": "giving a thumbs up",
    "Celebrating": "celebrating with both arms raised",
}
PROHIBIDO = ["text", "letters", "words", "titles", "captions", "numbers", "digits", "watermark", "logo",
             "signature", "3D render", "photorealistic", "photograph", "realistic textures"]


_NOMBRES_COLOR = {
    "black": (0, 0, 0), "white": (255, 255, 255), "neon cyan": (0, 229, 255), "electric blue": (30, 90, 255),
    "navy blue": (11, 19, 43), "steel blue": (58, 80, 107), "teal": (91, 192, 190), "neon green": (57, 255, 20),
    "emerald green": (0, 168, 107), "magenta": (255, 0, 255), "purple": (128, 0, 255),
    "violet": (160, 90, 255), "red": (255, 30, 60), "neon orange": (251, 133, 0), "amber": (255, 183, 3),
    "golden yellow": (255, 214, 10), "lime green": (51, 255, 0), "gray": (128, 128, 128),
    "light gray": (200, 200, 200), "brown-orange": (224, 123, 26), "neon yellow": (255, 229, 0),
    "bright cyan": (0, 240, 240), "neon purple": (208, 64, 255), "hot pink": (255, 43, 214),
}


def nombre_color(hex_color: str) -> str:
    """'#fb8500' -> 'neon orange'. Evita meter códigos (con cifras) en los prompts."""
    h = hex_color.strip().lstrip("#")
    if len(h) != 6:
        return hex_color
    rgb = tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))
    return min(_NOMBRES_COLOR, key=lambda n: sum((a - b) ** 2 for a, b in zip(_NOMBRES_COLOR[n], rgb)))


def colores_texto(colores: list[str]) -> str:
    vistos: list[str] = []
    for c in colores:
        n = nombre_color(c) if c.strip().startswith("#") else c
        if n not in vistos:
            vistos.append(n)
    return ", ".join(vistos)


def extraer_paleta(imagenes: list[Path], n: int = 5) -> list[str]:
    """Colores dominantes (hex) combinando todas las referencias."""
    if not imagenes:
        return []
    miniaturas = []
    for p in imagenes[:8]:
        try:
            miniaturas.append(Image.open(p).convert("RGB").resize((96, 96)))
        except OSError:
            continue
    if not miniaturas:
        return []
    lienzo = Image.new("RGB", (96 * len(miniaturas), 96))
    for i, m in enumerate(miniaturas):
        lienzo.paste(m, (96 * i, 0))
    q = lienzo.quantize(colors=n, method=Image.Quantize.MEDIANCUT)
    pal = q.getpalette()[: n * 3]
    conteo = sorted(q.getcolors(), reverse=True)  # [(cuenta, índice)]
    return ["#{:02x}{:02x}{:02x}".format(*pal[i * 3 : i * 3 + 3]) for _, i in conteo]


_COMILLAS = re.compile(r"(?:\b(?:reading|saying|that says|labeled|labelled|titled|with the words?)\s*)?"
                       r"[\"'“”‘’«»][^\"“”‘’«»]*[\"“”‘’«»']")
_NUMEROS = re.compile(r"(?:[$€£¥]\s?)?(?<![A-Za-z])\d+(?:[.,]\d+)*(?:\s?(?:%|k|K|M)\b|%)?(?!D\b)|\bx\d+\b")


def limpiar_prompt(texto: str) -> str:
    """Quita lo que un generador dibujaría como texto: citas entre comillas y cifras.

    "a sign reading 'SALE'" -> "a sign"; "a chart showing 50% growth" -> "a chart showing growth".
    Respeta "2D".
    """
    texto = _COMILLAS.sub("", texto)
    texto = _NUMEROS.sub("", texto)
    return re.sub(r"\s{2,}", " ", re.sub(r"\s+([,.;])", r"\1", texto)).strip(" ,;")


class BibliaEstilo:
    def __init__(self, proyecto: Proyecto, cfg: dict | None = None):
        da = (cfg or {}).get("direccion_arte", {}) or {}
        self.proyecto = proyecto
        self.estilo = proyecto.estilo
        self.descripcion = self.estilo.descripcion or da.get("estilo", ESTILO_NEON)
        self.expresiones = list(da.get("expresiones", EXPRESIONES))
        self.poses = list(da.get("poses", POSES))
        self.prohibido = list(da.get("prohibido", PROHIBIDO))
        self.paleta = self.estilo.paleta or extraer_paleta(proyecto.referencias)
        self.semilla = semilla(proyecto.slug)

    # ------------------------------------------------------------- para el guionista
    @property
    def nombres_personajes(self) -> list[str]:
        return list(self.estilo.personajes)

    def resumen_para_guionista(self) -> str:
        """Universo visual que se entrega a Claude para que respete personajes y reglas."""
        t = self.estilo.tematica
        lineas = []
        if self.proyecto.nicho:
            lineas.append(f"Nicho del canal '{self.proyecto.nombre}': {self.proyecto.nicho}")
        lineas.append(f"Estilo obligatorio de TODAS las imágenes: {self.descripcion}")
        if t:
            lineas.append(f"Temática activa: {t}")
        if self.paleta:
            lineas.append(f"Paleta general: {', '.join(self.paleta)}")
        if self.estilo.personajes:
            lineas.append("Personajes oficiales (usa SOLO estos, con su rol y colores):")
            for p in self.estilo.personajes.values():
                extra = f" | rol: {p.rol}" if p.rol else ""
                extra += f" | personalidad: {p.personalidad}" if p.personalidad else ""
                extra += f" | colores: {', '.join(p.colores)}" if p.colores else ""
                lineas.append(f"  - {p.nombre}{extra} | aspecto: {p.descripcion_para(t)}")
        for nombre, desc in self.estilo.escenarios.items():
            lineas.append(f"Escenario '{nombre}': {desc}")
        lineas.append(f"Expresiones oficiales: {', '.join(self.expresiones)}")
        lineas.append(f"Poses oficiales: {', '.join(self.poses)}")
        lineas.append(f"PROHIBIDO en las imágenes: {', '.join(self.prohibido)}")
        for regla in self.proyecto.reglas_extra:
            lineas.append(f"Regla del canal: {regla}")
        return "\n".join(lineas)

    # ------------------------------------------------------------- para el generador
    def negativo(self) -> str:
        return ", ".join(self.prohibido)

    def _reparto(self, escena: Escena) -> list[dict]:
        if escena.reparto:
            return escena.reparto
        # Compatibilidad: escenas sin reparto explícito (guion manual / plantilla)
        texto = f"{escena.prompt_visual} {escena.narracion}".lower()
        return [{"personaje": n, "expresion": "Talking", "pose": "Explaining"}
                for n in self.estilo.personajes if n in escena.personajes or n.lower() in texto]

    def prompt_final(self, escena: Escena, encuadre: str = "16:9 widescreen", max_chars: int = 1400) -> str:
        """Prompt completo. Si excede `max_chars`, se acorta la descripción de la escena,
        nunca el estilo, las fichas de personaje ni las prohibiciones."""
        escena_txt = limpiar_prompt(escena.prompt_visual)
        prompt = self._componer(escena, escena_txt, encuadre)
        exceso = len(prompt) - max_chars
        if exceso > 0:
            palabras = escena_txt.split()
            while palabras and len(" ".join(palabras)) > max(0, len(escena_txt) - exceso):
                palabras.pop()
            prompt = self._componer(escena, " ".join(palabras), encuadre)
        return prompt

    def _componer(self, escena: Escena, escena_txt: str, encuadre: str) -> str:
        t = self.estilo.tematica
        partes = [self.descripcion, f"scene: {escena_txt}" if escena_txt else ""]
        for r in self._reparto(escena):
            p = self.estilo.personajes.get(r.get("personaje", ""))
            if p is None:
                continue
            ficha = f"{p.nombre} ({p.rol}" if p.rol else f"{p.nombre} ("
            ficha += f"; colors {colores_texto(p.colores)}" if p.colores else ""
            ficha += f"): {p.descripcion_para(t)}"
            if r.get("expresion"):
                ficha += f", {r['expresion'].lower()} expression"
            if r.get("pose"):
                ficha += f", pose: {POSES_DESCRIPCION.get(r['pose'], limpiar_prompt(r['pose']))}"
            if r.get("accion"):
                ficha += f", {limpiar_prompt(r['accion'])}"
            partes.append(ficha.replace("(:", ":").replace("()", ""))
        if escena.escenario and escena.escenario in self.estilo.escenarios:
            partes.append(self.estilo.escenarios[escena.escenario])
        if self.paleta:
            partes.append(f"color palette: {colores_texto(self.paleta)}")
        partes.append(f"{encuadre} composition, consistent character design, same art style")
        partes.append("absolutely no " + ", no ".join(self.prohibido))
        return ", ".join(x.strip().rstrip(".") for x in partes if x and x.strip())
