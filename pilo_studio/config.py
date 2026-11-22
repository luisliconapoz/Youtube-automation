"""Carga y fusión de configuración (global + por proyecto)."""

from __future__ import annotations

import copy
import os
import re
from pathlib import Path
from typing import Any

import yaml

RAIZ = Path(__file__).resolve().parent.parent
CONFIG_GLOBAL = RAIZ / "config" / "settings.yaml"


def _fusionar(base: dict, extra: dict) -> dict:
    """Fusión profunda: `extra` sobrescribe a `base`."""
    out = copy.deepcopy(base)
    for k, v in (extra or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _fusionar(out[k], v)
        else:
            out[k] = v
    return out


def cargar_yaml(ruta: Path) -> dict:
    if not ruta.exists():
        return {}
    with open(ruta, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def cargar_config(proyecto: Path | None = None, ruta_global: Path = CONFIG_GLOBAL) -> dict[str, Any]:
    cfg = cargar_yaml(ruta_global)
    if proyecto is not None:
        cfg = _fusionar(cfg, cargar_yaml(Path(proyecto) / "proyecto.yaml").get("config", {}))
    return cfg


_VAR = re.compile(r"\$\{(\w+)\}")


def expandir_ruta(texto: str) -> Path | None:
    """Expande ${VAR} y ~. Devuelve None si alguna variable no existe."""
    faltante = False

    def sustituir(m: re.Match) -> str:
        nonlocal faltante
        valor = os.environ.get(m.group(1))
        if valor is None:
            faltante = True
            return ""
        return valor

    expandido = _VAR.sub(sustituir, texto)
    if faltante:
        return None
    return Path(os.path.expanduser(expandido))


def carpeta_salida(cfg: dict) -> Path:
    """Resuelve la carpeta final (OneDrive) con respaldos sensatos."""
    env = os.environ.get("PILO_OUTPUT_DIR")
    if env:
        return Path(env)
    destino = expandir_ruta(cfg.get("salida", {}).get("carpeta", "") or "")
    if destino is not None and str(destino) and destino.parent.exists():
        return destino
    return RAIZ / "salida"
