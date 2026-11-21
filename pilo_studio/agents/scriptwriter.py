"""Renderiza el system prompt del Agente Guionista para una marca y formato."""
from __future__ import annotations

import json
import re

from ..core import style
from ..core.brand import load_brand
from ..core.formats import LONG, SHORT, get_format
from ..core.paths import AGENTS_DIR, OUTPUT_DIR, SCHEMAS_DIR
from ..ideas.registry import IdeaRegistry

TEMPLATE = AGENTS_DIR / "scriptwriter_system_prompt.md"


def _characters_block(brand) -> str:
    rows = []
    for c in brand.characters.values():
        acc = ", ".join(c.accessories) or "—"
        tag = " **(NARRADOR)**" if c.id == brand.narrator else ""
        rows.append(
            f"- **{c.id}**{tag} — color {c.color_name} ({c.hex}); diseño: {c.design}; "
            f"accesorios: {acc}; personalidad: {', '.join(c.personality)}. Función: {c.role}"
        )
    return "\n".join(rows)


def build_system_prompt(brand_id: str, fmt_name: str, output_dir=OUTPUT_DIR, max_ideas: int = 60) -> str:
    brand = load_brand(brand_id)
    fmt = get_format(fmt_name)
    titles = IdeaRegistry(brand.id, output_dir).titles()[-max_ideas:]
    schema = json.loads((SCHEMAS_DIR / "video_plan.schema.json").read_text(encoding="utf-8"))
    values = {
        "BRAND_NAME": brand.display_name,
        "FORMAT": "VIDEO LARGO (16:9)" if fmt.name == "LONG" else "SHORT (9:16)",
        "LANGUAGE": {"en": "inglés (English)", "es": "español"}.get(brand.language, brand.language),
        "NICHE": brand.niche,
        "FOCUS": brand.focus,
        "TOPICS": "; ".join(brand.topics),
        "COLOR_RULE": brand.color_rule or "Combinar los colores oficiales.",
        "NARRATOR": brand.narrator,
        "CHARACTERS": _characters_block(brand),
        "EXISTING_IDEAS": "\n".join(f"- {t}" for t in titles) or "- (ninguna todavía)",
        "WPM": str(fmt.words_per_minute),
        "WPM_LONG": str(LONG.words_per_minute),
        "WPM_SHORT": str(SHORT.words_per_minute),
        "LONG_SCENE_MIN": f"{LONG.scene_min_seconds:g}",
        "LONG_SCENE_MAX": f"{LONG.scene_max_seconds:g}",
        "SHORT_SCENE_MIN": f"{SHORT.scene_min_seconds:g}",
        "SHORT_SCENE_MAX": f"{SHORT.scene_max_seconds:g}",
        "SCENE_MIN": f"{fmt.scene_min_seconds:g}",
        "SCENE_MAX": f"{fmt.scene_max_seconds:g}",
        "EXPRESSIONS": ", ".join(style.EXPRESSIONS),
        "POSES": ", ".join(style.POSES),
        "SCHEMA": json.dumps(schema, ensure_ascii=False, indent=1),
        "DURATION_RANGE": f"{fmt.target_min_seconds}–{fmt.target_max_seconds} s",
        "HOOK_MAX": f"{fmt.hook_max_seconds:g}",
    }
    text = TEMPLATE.read_text(encoding="utf-8")
    for k, v in values.items():
        text = text.replace("{{" + k + "}}", v)
    leftover = re.findall(r"\{\{[A-Z_]+\}\}", text)
    if leftover:
        raise ValueError(f"Placeholders sin rellenar en el system prompt: {leftover}")
    return text


def build_user_prompt(brand_id: str, fmt_name: str, topic: str | None = None) -> str:
    brand = load_brand(brand_id)
    t = f"Tema: {topic}." if topic else "Tema: elige tú la mejor idea nueva según los criterios de la sección 2."
    return (
        f"Marca: {brand.id}. Formato: {fmt_name.upper()}. {t} "
        "Entrega el plan completo en JSON siguiendo todas las reglas."
    )
