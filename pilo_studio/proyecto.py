"""Un *proyecto* = una idea del usuario + sus referencias visuales.

Estructura en disco:
    proyectos/<nombre>/
        idea.md            <- la idea temática central (lo único obligatorio)
        proyecto.yaml      <- estilo, personajes, escenarios y overrides de config
        referencias/       <- imágenes de referencia (personajes, escenarios, paleta)
        guion.yaml         <- (opcional) guion escrito a mano
        build/<formato>/   <- artefactos intermedios (caché reanudable)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from pilo_studio.config import cargar_yaml
from pilo_studio.utils import slug

EXT_IMAGEN = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}


@dataclass
class Estilo:
    descripcion: str = "ilustración digital cinematográfica, alto detalle"
    paleta: list[str] = field(default_factory=list)
    personajes: dict[str, str] = field(default_factory=dict)
    escenarios: dict[str, str] = field(default_factory=dict)


@dataclass
class Proyecto:
    ruta: Path
    nombre: str
    idea: str
    estilo: Estilo
    referencias: list[Path]

    @property
    def slug(self) -> str:
        return slug(self.nombre)

    def build(self, formato: str) -> Path:
        d = self.ruta / "build" / formato
        d.mkdir(parents=True, exist_ok=True)
        return d

    @property
    def guion_manual(self) -> Path:
        return self.ruta / "guion.yaml"

    @classmethod
    def cargar(cls, ruta: Path | str) -> "Proyecto":
        ruta = Path(ruta).resolve()
        idea_md = ruta / "idea.md"
        if not idea_md.exists():
            raise FileNotFoundError(f"Falta {idea_md}: escribe ahí la idea del video.")
        meta = cargar_yaml(ruta / "proyecto.yaml")
        e = meta.get("estilo", {}) or {}
        estilo = Estilo(
            descripcion=e.get("descripcion", Estilo.descripcion),
            paleta=list(e.get("paleta", []) or []),
            personajes=dict(e.get("personajes", {}) or {}),
            escenarios=dict(e.get("escenarios", {}) or {}),
        )
        refs_dir = ruta / "referencias"
        refs = sorted(p for p in refs_dir.glob("*") if p.suffix.lower() in EXT_IMAGEN) if refs_dir.exists() else []
        return cls(
            ruta=ruta,
            nombre=meta.get("nombre", ruta.name),
            idea=idea_md.read_text(encoding="utf-8").strip(),
            estilo=estilo,
            referencias=refs,
        )
