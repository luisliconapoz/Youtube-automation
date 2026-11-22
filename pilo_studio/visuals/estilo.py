"""Biblia de estilo: garantiza consistencia visual entre escenas.

Estrategias (todas de costo cero):
  1. Prefijo de estilo idéntico en cada prompt.
  2. Descripción canónica de cada personaje/escenario inyectada cuando aparece.
  3. Paleta de color extraída automáticamente de las imágenes de referencia.
  4. Semilla fija por proyecto (mismo 'look' en el generador).
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from pilo_studio.models import Escena
from pilo_studio.proyecto import Proyecto
from pilo_studio.utils import semilla


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


class BibliaEstilo:
    def __init__(self, proyecto: Proyecto):
        self.proyecto = proyecto
        self.estilo = proyecto.estilo
        self.paleta = self.estilo.paleta or extraer_paleta(proyecto.referencias)
        self.semilla = semilla(proyecto.slug)

    def resumen_para_guionista(self) -> str:
        """Texto que se entrega al LLM para que respete el universo visual."""
        lineas = [f"Estilo visual: {self.estilo.descripcion}"]
        if self.paleta:
            lineas.append(f"Paleta de color: {', '.join(self.paleta)}")
        for nombre, desc in self.estilo.personajes.items():
            lineas.append(f"Personaje '{nombre}': {desc}")
        for nombre, desc in self.estilo.escenarios.items():
            lineas.append(f"Escenario '{nombre}': {desc}")
        return "\n".join(lineas)

    def prompt_final(self, escena: Escena) -> str:
        partes = [self.estilo.descripcion, escena.prompt_visual]
        texto_escena = f"{escena.prompt_visual} {escena.narracion}".lower()
        for nombre, desc in self.estilo.personajes.items():
            if nombre in escena.personajes or nombre.lower() in texto_escena:
                partes.append(f"{nombre}: {desc}")
        if escena.escenario and escena.escenario in self.estilo.escenarios:
            partes.append(self.estilo.escenarios[escena.escenario])
        if self.paleta:
            partes.append(f"color palette {' '.join(self.paleta)}")
        partes.append("consistent character design, same art style, no text")
        return ", ".join(p.strip().rstrip(".") for p in partes if p)
