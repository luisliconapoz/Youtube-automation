"""Imágenes de PRUEBA (gratis, sin IA): fondo negro + stickman neón del color oficial.
Solo para probar el Tubo de punta a punta. NO publicar videos hechos con esto."""
from __future__ import annotations

from pathlib import Path

from ..core.brand import load_brand
from .base import ImageProvider, ProviderResult

_POS = {"left": 0.28, "center": 0.5, "right": 0.72}


class PlaceholderImages(ImageProvider):
    name = "placeholder"

    def __init__(self, brand_id: str):
        self.brand = load_brand(brand_id)

    def generate(self, prompt: dict, out_path: Path) -> ProviderResult:
        from PIL import Image, ImageDraw, ImageFilter
        w, h = prompt["width"], prompt["height"]
        base = Image.new("RGB", (w, h), "black")
        glow = Image.new("RGB", (w, h), "black")
        chars = prompt.get("characters") or []
        slots = ["center"] if len(chars) == 1 else ["left", "right", "center"][: len(chars)]
        u = min(w, h) / 10
        for cid, slot in zip(chars, slots):
            col = self.brand.character(cid).hex
            cx, cy = int(w * _POS[slot]), int(h * 0.48)
            for img, width in ((glow, int(u * 0.35)), (base, int(u * 0.12))):
                d = ImageDraw.Draw(img)
                r = int(u * 0.9)
                d.ellipse([cx - r, cy - 3 * r, cx + r, cy - r], outline=col, width=width, fill="black")
                d.line([cx, cy - r, cx, cy + 2 * r], fill=col, width=width)
                d.line([cx - 2 * r, cy - 0.2 * r, cx + 2 * r, cy + 0.4 * r], fill=col, width=width)
                d.line([cx, cy + 2 * r, cx - 1.2 * r, cy + 4 * r], fill=col, width=width)
                d.line([cx, cy + 2 * r, cx + 1.2 * r, cy + 4 * r], fill=col, width=width)
                for ex in (-0.35, 0.35):
                    d.ellipse([cx + (ex - 0.18) * r, cy - 2.3 * r, cx + (ex + 0.18) * r, cy - 1.9 * r], fill="white")
        glow = glow.filter(ImageFilter.GaussianBlur(u * 0.25))
        out = Image.blend(base, glow, 0.35)
        out.paste(base, mask=base.convert("L").point(lambda v: 255 if v > 20 else 0))
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out.save(out_path)
        return ProviderResult(out_path, usd=0.0, units=1)
