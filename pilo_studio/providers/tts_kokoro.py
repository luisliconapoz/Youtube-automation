"""Voz gratis y local con Kokoro (ONNX, solo CPU). Descarga el modelo la primera vez."""
from __future__ import annotations

import os
import urllib.request
from pathlib import Path

from .base import ProviderResult, TTSProvider

BASE = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/"
FILES = ("kokoro-v1.0.int8.onnx", "voices-v1.0.bin")
MODELS_DIR = Path(os.environ.get("PILO_MODELS_DIR", Path.home() / ".cache" / "pilo" / "kokoro"))


def ensure_models(d: Path = MODELS_DIR) -> Path:
    d.mkdir(parents=True, exist_ok=True)
    for f in FILES:
        if not (d / f).exists():
            urllib.request.urlretrieve(BASE + f, d / f)
    return d


def trim_silence(audio, sr: int, threshold: float = 0.01, pad_ms: int = 60):
    import numpy as np
    idx = np.where(np.abs(audio) > threshold)[0]
    if not len(idx):
        return audio
    pad = int(sr * pad_ms / 1000)
    return audio[max(idx[0] - pad, 0): idx[-1] + pad]


class KokoroTTS(TTSProvider):
    name = "kokoro"

    def __init__(self, models_dir: Path = MODELS_DIR):
        from kokoro_onnx import Kokoro
        d = ensure_models(models_dir)
        self.k = Kokoro(str(d / FILES[0]), str(d / FILES[1]))

    def synthesize(self, text: str, voice: dict, out_path: Path) -> ProviderResult:
        import soundfile as sf
        lang = voice.get("lang", "en-us")
        audio, sr = self.k.create(text, voice=voice.get("voice_id") or "am_michael",
                                  speed=float(voice.get("speed", 1.0)), lang=lang)
        audio = trim_silence(audio, sr)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        sf.write(str(out_path), audio, sr)
        return ProviderResult(out_path, usd=0.0, units=len(text))
