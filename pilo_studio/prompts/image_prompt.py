"""Convierte cada escena del plan en un prompt de imagen final, numerado y determinista.

El guionista solo dirige (quién, expresión, pose, acción, escenario). Este módulo
añade SIEMPRE: estilo PILO, diseño canónico del personaje (color + accesorios),
fondo negro, negativo anti-texto/anti-3D, formato y referencias visuales.
Así ningún prompt puede "olvidar" una regla de la biblia.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

from ..core import style
from ..core.brand import Brand
from ..core.formats import get_format
from ..core.paths import REFERENCES_DIR

_IMG_EXT = {".png", ".jpg", ".jpeg", ".webp"}
_CAMERA = {
    "wide": "wide shot, full bodies visible",
    "medium": "medium shot",
    "close-up": "close-up on the face and hands",
}


@dataclass
class ImagePrompt:
    number: int
    filename: str              # 001.png
    prompt: str
    negative_prompt: str
    aspect: str
    width: int
    height: int
    characters: list[str]
    reference_images: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def reference_images_for(brand_id: str, char_id: str, refs_dir: Path = REFERENCES_DIR) -> list[str]:
    folder = refs_dir / brand_id / char_id
    if not folder.is_dir():
        return []
    # Solo ref_*: las hojas de expresiones (cuadrículas) no se adjuntan a escenas
    return sorted(str(p) for p in folder.iterdir()
                  if p.suffix.lower() in _IMG_EXT and p.name.lower().startswith("ref"))


def _deidentify(text: str, brand: Brand) -> str:
    """Reemplaza IDs de personaje (BLUE, RICH…) por descripciones visuales, para que
    el generador no escriba el nombre como texto ni confunda 'BLUE' con un color."""
    names = {}
    for c in brand.characters.values():
        for n in (c.id, *c.aliases):
            names[n] = c.short_ref()
    if not names:
        return text
    pat = re.compile(r"\b(" + "|".join(sorted(map(re.escape, names), key=len, reverse=True)) + r")\b")
    return pat.sub(lambda m: names[m.group(1)], text)


def build_scene_prompt(scene: dict, brand: Brand, fmt_name: str, refs_dir: Path = REFERENCES_DIR) -> ImagePrompt:
    fmt = get_format(fmt_name)
    n = int(scene["number"])
    parts = [style.STYLE_PREAMBLE]
    char_ids, refs = [], []

    for ch in scene.get("characters", []):
        c = brand.character(ch["id"])
        char_ids.append(c.id)
        pos = ch.get("position")
        bits = [
            c.visual_description(),
            style.EXPRESSION_PROMPTS[ch["expression"]],
            style.POSE_PROMPTS[ch["pose"]],
        ]
        if ch.get("action"):
            bits.append(_deidentify(ch["action"], brand))
        if pos:
            bits.append(f"positioned {pos} of frame")
        parts.append("; ".join(bits))
        refs += reference_images_for(brand.id, c.id, refs_dir)

    parts.append(f"Main visual idea: {_deidentify(scene['visual_idea'], brand)}")
    parts.append(f"Setting: {_deidentify(scene['setting'], brand)}, on a {style.BACKGROUND_RULE}")
    if scene.get("key_objects"):
        parts.append("Key objects with soft neon glow: " + ", ".join(scene["key_objects"]))
    parts.append(_CAMERA.get(scene.get("camera", "medium"), "medium shot"))
    if fmt.name == "SHORT":
        parts.append("vertical 9:16 composition, subject centered in the middle third, empty space top and bottom for captions")
    else:
        parts.append("horizontal 16:9 composition, leave the lower third clean for subtitles")
    parts.append("keep official character design, proportions and colors exactly as reference; "
                 "no text, no letters, no numbers anywhere in the image")

    return ImagePrompt(
        number=n,
        filename=f"{n:03d}.png",
        prompt=". ".join(parts) + ".",
        negative_prompt=style.NEGATIVE_PROMPT,
        aspect=fmt.aspect,
        width=fmt.width,
        height=fmt.height,
        characters=char_ids,
        reference_images=sorted(set(refs)),
    )


def build_all_prompts(plan: dict, brand: Brand, refs_dir: Path = REFERENCES_DIR) -> list[ImagePrompt]:
    return [build_scene_prompt(s, brand, plan["format"], refs_dir) for s in plan["scenes"]]


def prompts_markdown(plan: dict, prompts: list[ImagePrompt]) -> str:
    """Documento legible (para revisión humana o para copiar/pegar en Flow/Higgsfield)."""
    out = [f"# {plan['brand']} — {plan['title']}", f"Formato: {plan['format']} · {len(prompts)} imágenes", ""]
    by_num = {s["number"]: s for s in plan["scenes"]}
    for p in prompts:
        sc = by_num[p.number]
        cast = ", ".join(f"{c['id']} ({c['expression']}/{c['pose']})" for c in sc["characters"]) or "sin personajes"
        out += [
            f"## Image {p.number:03d} — {sc['section_id']} · {sc['duration_s']}s",
            f"**Narración:** {sc['narration']}",
            f"**Reparto:** {cast}",
            f"**Prompt:** {p.prompt}",
            f"**Negativo:** {p.negative_prompt}",
            f"**Referencias:** {', '.join(p.reference_images) or '— (añade imágenes en references/' + plan['brand'] + '/<PERSONAJE>/)'}",
            "",
        ]
    return "\n".join(out)
