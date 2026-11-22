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
class Personaje:
    """Personaje oficial del universo: rol, colores y aspecto canónico."""

    nombre: str
    descripcion: str
    rol: str = ""
    colores: list[str] = field(default_factory=list)
    variantes: dict[str, str] = field(default_factory=dict)  # temática -> descripción alternativa

    def descripcion_para(self, tematica: str | None) -> str:
        return self.variantes.get(tematica or "", self.descripcion)

    @classmethod
    def desde(cls, nombre: str, datos) -> "Personaje":
        if isinstance(datos, str):
            return cls(nombre, datos)
        datos = datos or {}
        return cls(nombre, datos.get("descripcion", ""), datos.get("rol", ""),
                   list(datos.get("colores", []) or []), dict(datos.get("variantes", {}) or {}))


@dataclass
class Estilo:
    descripcion: str = ""                  # vacío = usa direccion_arte.estilo de settings.yaml
    paleta: list[str] = field(default_factory=list)
    personajes: dict[str, Personaje] = field(default_factory=dict)
    escenarios: dict[str, str] = field(default_factory=dict)
    tematica: str | None = None            # p. ej. "Money Lab" o "Wild Money" (elige variantes)


@dataclass
class Proyecto:
    ruta: Path
    nombre: str
    idea: str
    estilo: Estilo
    referencias: list[Path]
    provisional: bool = False   # personajes aún sin la guía oficial

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
            descripcion=e.get("descripcion", "") or "",
            paleta=list(e.get("paleta", []) or []),
            personajes={n: Personaje.desde(n, d) for n, d in (e.get("personajes", {}) or {}).items()},
            escenarios=dict(e.get("escenarios", {}) or {}),
            tematica=e.get("tematica") or meta.get("tematica"),
        )
        refs_dir = ruta / "referencias"
        refs = sorted(p for p in refs_dir.glob("*") if p.suffix.lower() in EXT_IMAGEN) if refs_dir.exists() else []
        return cls(
            ruta=ruta,
            nombre=meta.get("nombre", ruta.name),
            idea=idea_md.read_text(encoding="utf-8").strip(),
            estilo=estilo,
            referencias=refs,
            provisional=bool(meta.get("provisional", False)),
        )

    @staticmethod
    def cargar_meta(ruta: Path | str) -> dict:
        """Lectura ligera de proyecto.yaml (sin necesidad de idea.md)."""
        meta = cargar_yaml(Path(ruta) / "proyecto.yaml")
        return {"nombre": meta.get("nombre", Path(ruta).name),
                "personajes": list(((meta.get("estilo") or {}).get("personajes") or {}).keys()),
                "provisional": bool(meta.get("provisional", False))}
