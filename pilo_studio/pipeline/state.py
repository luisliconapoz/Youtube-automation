"""Estado reanudable por video + libro de costos.

Si el proceso se corta (apagón, error de API, GPU ocupada) se vuelve a lanzar y
continúa desde la última etapa completada: nunca se paga dos veces lo ya hecho.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path


class Stage(str, Enum):
    PLAN = "PLAN"                    # Idea → Estructura → Guion (Agente Guionista)
    QA_PLAN = "QA_PLAN"              # Gate 1: reglas de marca/formato antes de gastar
    IMAGE_PROMPTS = "IMAGE_PROMPTS"  # Prompts numerados 001, 002…
    IMAGES = "IMAGES"                # Imágenes numeradas 001.png…
    QA_IMAGES = "QA_IMAGES"          # Gate 2: imágenes completas, tamaño, fondo negro
    VOICE = "VOICE"                  # Locución por escena
    SUBTITLES = "SUBTITLES"          # SRT sincronizado
    AUDIO_MIX = "AUDIO_MIX"          # Voz + música sin copyright + SFX (ducking)
    RENDER = "RENDER"                # Remotion / Adobe → final.mp4
    QA_FINAL = "QA_FINAL"            # Gate 3: duración, audio, resolución
    PUBLISH_DRAFT = "PUBLISH_DRAFT"  # Borrador de metadatos; copia a LISTOS/. Publicación MANUAL.


ORDER = list(Stage)


class Status(str, Enum):
    PENDING = "pending"
    DONE = "done"
    FAILED = "failed"
    BLOCKED = "blocked"     # falta un proveedor/insumo; no es un error del contenido


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class PipelineState:
    def __init__(self, path: Path):
        self.path = Path(path)
        if self.path.exists():
            self.data = json.loads(self.path.read_text(encoding="utf-8"))
        else:
            self.data = {"created_at": _now(), "stages": {s.value: {"status": Status.PENDING.value, "attempts": 0} for s in ORDER}}
            self.save()

    def save(self):
        self.path.write_text(json.dumps(self.data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def get(self, stage: Stage) -> dict:
        return self.data["stages"][stage.value]

    def status(self, stage: Stage) -> Status:
        return Status(self.get(stage)["status"])

    def mark(self, stage: Stage, status: Status, **extra):
        rec = self.get(stage)
        rec.update(status=status.value, updated_at=_now(), **extra)
        self.save()

    def bump_attempt(self, stage: Stage) -> int:
        rec = self.get(stage)
        rec["attempts"] = rec.get("attempts", 0) + 1
        self.save()
        return rec["attempts"]

    def next_stage(self) -> Stage | None:
        for s in ORDER:
            if self.status(s) != Status.DONE:
                return s
        return None

    def reset_from(self, stage: Stage):
        """Re-ejecutar desde una etapa (p. ej. tras corregir el plan)."""
        hit = False
        for s in ORDER:
            hit = hit or s == stage
            if hit:
                self.data["stages"][s.value] = {"status": Status.PENDING.value, "attempts": 0}
        self.save()


class CostLedger:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.entries: list[dict] = json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else []

    def add(self, stage: str, provider: str, usd: float, units: float = 0, note: str = ""):
        self.entries.append({"at": _now(), "stage": stage, "provider": provider, "usd": round(usd, 4), "units": units, "note": note})
        self.path.write_text(json.dumps(self.entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    @property
    def total(self) -> float:
        return round(sum(e["usd"] for e in self.entries), 4)


class BudgetExceeded(RuntimeError):
    pass


class ProviderNotConfigured(RuntimeError):
    """La etapa necesita un proveedor (GPU, API, Remotion) que aún no está conectado."""
