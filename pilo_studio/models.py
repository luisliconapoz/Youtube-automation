"""Modelos de datos que viajan entre las fases del pipeline."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class Palabra:
    """Marca temporal de una palabra (segundos, relativa a la escena)."""

    texto: str
    inicio: float
    fin: float


@dataclass
class Escena:
    id: int
    narracion: str                     # texto exacto para la voz
    prompt_visual: str                 # descripción de la imagen
    titulo: str | None = None          # título visible en pantalla: "Imagen N — titulo"
    personajes: list[str] = field(default_factory=list)
    escenario: str | None = None
    # [{"personaje": "Cyan", "expresion": "Thinking", "pose": "hand on chin"}]
    reparto: list[dict] = field(default_factory=list)
    # --- Rellenado por las fases siguientes ---
    audio: str | None = None
    duracion: float | None = None
    palabras: list[Palabra] = field(default_factory=list)
    imagen: str | None = None

    @classmethod
    def desde_dict(cls, d: dict) -> "Escena":
        d = dict(d)
        d["palabras"] = [Palabra(**p) for p in d.get("palabras", [])]
        d["reparto"] = [dict(r) for r in d.get("reparto", []) or []]
        if d["reparto"] and not d.get("personajes"):
            d["personajes"] = [r.get("personaje") for r in d["reparto"] if r.get("personaje")]
        campos = cls.__dataclass_fields__
        return cls(**{k: v for k, v in d.items() if k in campos})


@dataclass
class Guion:
    titulo: str
    formato: str                       # "largo" | "short"
    descripcion: str = ""
    etiquetas: list[str] = field(default_factory=list)
    miniatura_texto: str = ""          # 2-5 palabras impactantes para la miniatura
    miniatura_prompt: str = ""         # descripción visual de la miniatura
    codigo: str | None = None          # código del video (p.ej. FS-001): carpeta de salida y nombre de archivos
    escenas: list[Escena] = field(default_factory=list)

    @property
    def total_palabras(self) -> int:
        return sum(len(e.narracion.split()) for e in self.escenas)

    def guardar(self, ruta: Path) -> None:
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def cargar(cls, ruta: Path) -> "Guion":
        return cls.desde_dict(json.loads(Path(ruta).read_text(encoding="utf-8")))

    @classmethod
    def desde_dict(cls, d: dict) -> "Guion":
        return cls(
            titulo=d.get("titulo", "Sin título"),
            formato=d.get("formato", "largo"),
            descripcion=d.get("descripcion", ""),
            etiquetas=list(d.get("etiquetas", [])),
            miniatura_texto=d.get("miniatura_texto", ""),
            miniatura_prompt=d.get("miniatura_prompt", ""),
            codigo=d.get("codigo"),
            escenas=[Escena.desde_dict({"id": i + 1, **e}) for i, e in enumerate(d.get("escenas", []))],
        )
