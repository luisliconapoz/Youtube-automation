"""Interfaces de proveedores. Cada herramienta (Open Generative AI, Google Flow,
Higgsfield, Kokoro, VoiceStudio, ElevenLabs, Remotion, Adobe…) se conecta
implementando UNA de estas clases. El orquestador nunca conoce la herramienta
concreta: así se cambia de proveedor sin tocar el Tubo.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ProviderResult:
    path: Path | None = None
    usd: float = 0.0          # costo real de la llamada (0 para local)
    units: float = 0.0        # imágenes, caracteres, segundos…
    meta: dict | None = None


class LLMProvider(ABC):
    name = "llm"

    def complete(self, system: str, messages: list[dict]) -> str:
        raise NotImplementedError

    def parse(self, text: str) -> dict:
        from .llm_claude import extract_json
        return extract_json(text)

    def generate_plan(self, system_prompt: str, user_prompt: str) -> dict:
        """Devuelve el plan de video (dict que cumple schemas/video_plan.schema.json)."""
        return self.parse(self.complete(system_prompt, [{"role": "user", "content": user_prompt}]))

    def estimate_usd(self) -> float:
        return 0.0


class ImageProvider(ABC):
    name = "image"

    @abstractmethod
    def generate(self, prompt: dict, out_path: Path) -> ProviderResult:
        """prompt = ImagePrompt.to_dict(); debe escribir out_path (001.png…)."""

    def estimate_usd(self, n_images: int) -> float:
        return 0.0


class TTSProvider(ABC):
    name = "tts"

    @abstractmethod
    def synthesize(self, text: str, voice: dict, out_path: Path) -> ProviderResult:
        ...

    def estimate_usd(self, n_chars: int) -> float:
        return 0.0


class Renderer(ABC):
    name = "render"

    @abstractmethod
    def render(self, project_root: Path, timeline: dict, out_path: Path) -> ProviderResult:
        ...
