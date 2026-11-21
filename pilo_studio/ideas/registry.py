"""Registro de ideas por marca (Paso 1 del Tubo: generar idea y GUARDARLA).

Evita repetir ideas o ángulos desgastados: cada idea nueva se compara contra
todas las ya registradas de la misma marca antes de aceptarse.
Almacenamiento: output/<BRAND>/ideas.jsonl (una idea por línea, append-only).
"""
from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path

from ..core.paths import OUTPUT_DIR

_STOP = {
    "the", "a", "an", "of", "to", "and", "in", "how", "why", "what", "is", "are",
    "your", "you", "this", "that", "for", "on", "with", "really", "actually",
    "el", "la", "los", "las", "de", "del", "y", "en", "como", "cómo", "por", "que",
    "qué", "un", "una", "tu", "su", "es",
}

DUPLICATE_THRESHOLD = 0.72   # >= se rechaza como repetida
SIMILAR_THRESHOLD = 0.50     # >= se avisa (ángulo parecido)


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9 ]+", " ", text)


def _tokens(text: str) -> set[str]:
    return {t for t in _normalize(text).split() if t not in _STOP and len(t) > 2}


def similarity(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    jacc = len(ta & tb) / len(ta | tb) if ta | tb else 0.0
    seq = SequenceMatcher(None, " ".join(sorted(ta)), " ".join(sorted(tb))).ratio()
    return max(jacc, 0.6 * seq + 0.4 * jacc)


class IdeaRegistry:
    def __init__(self, brand_id: str, output_dir: Path = OUTPUT_DIR):
        self.brand_id = brand_id
        self.path = output_dir / brand_id / "ideas.jsonl"

    def all(self) -> list[dict]:
        if not self.path.exists():
            return []
        return [json.loads(l) for l in self.path.read_text(encoding="utf-8").splitlines() if l.strip()]

    @staticmethod
    def _key(idea: dict) -> str:
        return f"{idea.get('title', '')} {idea.get('angle', '')} {idea.get('topic', '')}"

    def check(self, idea: dict) -> tuple[str, list[tuple[float, dict]]]:
        """Devuelve ('new'|'similar'|'duplicate', [(score, idea_existente), ...])."""
        key = self._key(idea)
        scored = sorted(
            ((similarity(key, self._key(old)), old) for old in self.all()),
            key=lambda x: x[0], reverse=True,
        )
        top = [s for s in scored if s[0] >= SIMILAR_THRESHOLD][:5]
        if top and top[0][0] >= DUPLICATE_THRESHOLD:
            return "duplicate", top
        if top:
            return "similar", top
        return "new", []

    def add(self, idea: dict, force: bool = False) -> dict:
        status, matches = self.check(idea)
        if status == "duplicate" and not force:
            raise ValueError(
                f"Idea repetida para {self.brand_id}: '{idea.get('title')}' ≈ "
                f"'{matches[0][1].get('title')}' (similitud {matches[0][0]:.2f})"
            )
        record = {
            **idea,
            "brand": self.brand_id,
            "registered_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "status": idea.get("status", "planned"),
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        return record

    def titles(self) -> list[str]:
        return [i.get("title", "") for i in self.all()]
