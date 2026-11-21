"""Estructura de carpetas de cada video y nomenclatura numérica 001, 002, 003…

output/
  <BRAND>/
    ideas.jsonl                       ← registro anti-repetición
    LISTOS/                           ← MP4 finales listos para publicar A MANO
    proyectos/
      <YYYYMMDD>_<FORMAT>_<slug>/
        00_idea.json
        01_structure.json
        02_script.md
        plan.json                     ← plan completo del Agente Guionista
        qa_plan.txt
        03_prompts/001.json …  + prompts.md
        04_images/001.png …
        05_audio/voice_001.wav … , voice_full.wav, music.mp3, sfx/
        06_subtitles/subs.srt
        07_render/final.mp4
        08_publish/metadata_draft.md  ← borrador; publicación MANUAL
        state.json  costs.json  pipeline.log
"""
from __future__ import annotations

import json
import re
import unicodedata
from datetime import date
from pathlib import Path

from ..core.paths import OUTPUT_DIR

SUBDIRS = {
    "prompts": "03_prompts",
    "images": "04_images",
    "audio": "05_audio",
    "subtitles": "06_subtitles",
    "render": "07_render",
    "publish": "08_publish",
}


def slugify(text: str, max_len: int = 48) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text[:max_len].rstrip("-") or "video"


def num(n: int) -> str:
    return f"{n:03d}"


class Project:
    def __init__(self, root: Path):
        self.root = Path(root)

    # ---------- creación / apertura ----------
    @classmethod
    def create(cls, brand_id: str, fmt: str, title: str, output_dir: Path = OUTPUT_DIR,
               day: date | None = None) -> "Project":
        day = day or date.today()
        base = output_dir / brand_id / "proyectos"
        name = f"{day:%Y%m%d}_{fmt.upper()}_{slugify(title)}"
        root = base / name
        i = 2
        while root.exists():
            root = base / f"{name}-{i}"
            i += 1
        p = cls(root)
        p.ensure_dirs()
        return p

    def ensure_dirs(self):
        self.root.mkdir(parents=True, exist_ok=True)
        for d in SUBDIRS.values():
            (self.root / d).mkdir(exist_ok=True)

    def dir(self, key: str) -> Path:
        return self.root / SUBDIRS[key]

    @property
    def brand_dir(self) -> Path:
        return self.root.parents[1]

    @property
    def ready_dir(self) -> Path:
        d = self.brand_dir / "LISTOS"
        d.mkdir(parents=True, exist_ok=True)
        return d

    # ---------- archivos ----------
    def path(self, name: str) -> Path:
        return self.root / name

    def write_json(self, name: str, data) -> Path:
        p = self.root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return p

    def read_json(self, name: str):
        return json.loads((self.root / name).read_text(encoding="utf-8"))

    def write_text(self, name: str, text: str) -> Path:
        p = self.root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        return p

    def image_path(self, n: int) -> Path:
        return self.dir("images") / f"{num(n)}.png"

    def voice_path(self, n: int) -> Path:
        return self.dir("audio") / f"voice_{num(n)}.wav"

    def missing_images(self, count: int) -> list[int]:
        return [n for n in range(1, count + 1) if not self.image_path(n).exists()]

    def log(self, msg: str):
        from datetime import datetime
        with (self.root / "pipeline.log").open("a", encoding="utf-8") as f:
            f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S} {msg}\n")
