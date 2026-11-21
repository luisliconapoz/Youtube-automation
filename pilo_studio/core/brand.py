"""Carga de la biblia de marca y del registro modular de 10 canales."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .paths import BRANDS_DIR


@dataclass(frozen=True)
class Character:
    id: str
    brand_id: str
    color_name: str
    hex: str
    design: str
    accessories: tuple[str, ...]
    personality: tuple[str, ...]
    role: str
    aliases: tuple[str, ...] = ()
    color_en: str = ""

    def visual_description(self) -> str:
        """Descripción canónica para prompts de imagen (no varía nunca)."""
        acc = f", always with {', '.join(self.accessories)}" if self.accessories else ""
        # Sin códigos hex ni nombres propios: los modelos de imagen tienden a
        # dibujarlos como texto dentro de la imagen.
        return f"{self.design}, black body with glowing {self.color_name_en()} neon outline{acc}"

    def short_ref(self) -> str:
        return f"the {self.color_name_en()} neon stickman"

    def color_name_en(self) -> str:
        if self.color_en:
            return self.color_en
        return {
            "#00E5FF": "cyan", "#39FF14": "green", "#FF3EA5": "pink",
            "#FFE600": "yellow", "#FF2A2A": "red", "#FF8C00": "orange",
            "#00C2B2": "teal", "#A64DFF": "purple", "#B6FF00": "lime green",
            "#F5F5F5": "white", "#3DFFB4": "mint green", "#FF6F61": "coral",
            "#C0C7D0": "silver", "#D2B48C": "tan beige",
        }.get(self.hex.upper(), self.color_name)


@dataclass(frozen=True)
class Brand:
    id: str
    slot: int
    active: bool
    display_name: str
    language: str
    niche: str
    focus: str
    topics: tuple[str, ...]
    narrator: str
    color_rule: str
    characters: dict[str, Character]
    voice: dict = field(default_factory=dict)
    open_questions: tuple[str, ...] = ()

    def character(self, char_id: str) -> Character:
        key = char_id.strip().upper()
        if key in self.characters:
            return self.characters[key]
        for c in self.characters.values():
            if key in c.aliases:
                return c
        raise KeyError(
            f"El personaje {char_id!r} no pertenece a {self.id}. "
            f"Permitidos: {', '.join(self.characters)}"
        )

    def has_character(self, char_id: str) -> bool:
        try:
            self.character(char_id)
            return True
        except KeyError:
            return False


def load_brand(brand_id: str, brands_dir: Path = BRANDS_DIR) -> Brand:
    path = brands_dir / f"{brand_id.upper()}.json"
    if not path.exists():
        raise FileNotFoundError(f"No existe la biblia de marca {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    chars = {
        cid: Character(
            id=cid,
            brand_id=data["id"],
            color_name=c["color_name"],
            hex=c["hex"],
            design=c["design"],
            accessories=tuple(c.get("accessories", [])),
            personality=tuple(c.get("personality", [])),
            role=c["role"],
            aliases=tuple(a.upper() for a in c.get("aliases", [])),
            color_en=c.get("color_en", ""),
        )
        for cid, c in data["characters"].items()
    }
    if data["narrator"] not in chars:
        raise ValueError(f"{brand_id}: el narrador {data['narrator']} no está en characters")
    return Brand(
        id=data["id"],
        slot=data["slot"],
        active=data["active"],
        display_name=data["display_name"],
        language=data.get("language", "en"),
        niche=data["niche"],
        focus=data["focus"],
        topics=tuple(data["topics"]),
        narrator=data["narrator"],
        color_rule=data.get("color_rule", ""),
        characters=chars,
        voice=data.get("voice", {}),
        open_questions=tuple(data.get("open_questions", [])),
    )


def load_registry(brands_dir: Path = BRANDS_DIR) -> dict:
    return json.loads((brands_dir / "channels.json").read_text(encoding="utf-8"))


def active_brands(brands_dir: Path = BRANDS_DIR) -> list[Brand]:
    reg = load_registry(brands_dir)
    out = []
    for ch in sorted(reg["channels"], key=lambda c: c["slot"]):
        if ch["active"]:
            out.append(load_brand(ch["id"], brands_dir))
    return out


def check_character_exclusivity(brands: list[Brand]) -> list[str]:
    """Los personajes jamás se mezclan entre marcas: los IDs deben ser únicos."""
    seen: dict[str, str] = {}
    problems = []
    for b in brands:
        for cid, c in b.characters.items():
            for name in (cid, *c.aliases):
                if name in seen and seen[name] != b.id:
                    problems.append(f"{name} existe en {seen[name]} y en {b.id}")
                seen.setdefault(name, b.id)
    return problems
