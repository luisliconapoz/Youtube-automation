"""Imágenes con la API de Gemini (REST, solo urllib).

Clave: guardada como secreto de red del entorno (el proxy la inyecta) o en GEMINI_API_KEY.
Adjunta las referencias oficiales de cada personaje y pone margen negro final
(evita que copie el marco de la hoja de referencia y garantiza borde negro).
"""
from __future__ import annotations

import base64
import io
import json
import os
import urllib.request
from pathlib import Path

from .base import ImageProvider, ProviderResult

API = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


class GeminiImages(ImageProvider):
    name = "gemini"

    def __init__(self, model: str = "gemini-2.5-flash-image", usd_per_image: float = 0.04, timeout: int = 180):
        # Si la clave está guardada en el entorno, el proxy reemplaza este valor.
        self.key = os.environ.get("GEMINI_API_KEY", "proxy-injected")
        self.model, self.usd, self.timeout = model, usd_per_image, timeout

    def estimate_usd(self, n_images: int) -> float:
        return self.usd * n_images

    def generate(self, prompt: dict, out_path: Path) -> ProviderResult:
        from PIL import Image
        parts = [{"text": prompt["prompt"] + " Use the attached reference images ONLY for the exact character "
                  "design; do not copy their frames or borders. Negative: " + prompt["negative_prompt"]}]
        for ref in prompt.get("reference_images", [])[:3]:
            parts.append({"inline_data": {"mime_type": "image/png",
                                          "data": base64.b64encode(Path(ref).read_bytes()).decode()}})
        body = {"contents": [{"parts": parts}],
                "generationConfig": {"responseModalities": ["IMAGE"],
                                     "imageConfig": {"aspectRatio": prompt["aspect"]}}}
        req = urllib.request.Request(API.format(model=self.model), data=json.dumps(body).encode(),
                                     headers={"x-goog-api-key": self.key, "content-type": "application/json"})
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            data = json.loads(r.read())
        img_b64 = next((p["inlineData"]["data"] for c in data.get("candidates", [])
                        for p in c.get("content", {}).get("parts", []) if "inlineData" in p), None)
        if not img_b64:
            raise RuntimeError(f"Gemini no devolvió imagen: {str(data)[:300]}")
        im = Image.open(io.BytesIO(base64.b64decode(img_b64))).convert("RGB")
        w, h = prompt["width"], prompt["height"]
        inner = im.resize((int(w * 0.92), int(h * 0.92)), Image.LANCZOS)
        canvas = Image.new("RGB", (w, h), "black")
        canvas.paste(inner, ((w - inner.width) // 2, (h - inner.height) // 2))
        out_path.parent.mkdir(parents=True, exist_ok=True)
        canvas.save(out_path)
        return ProviderResult(out_path, usd=self.usd, units=1)
