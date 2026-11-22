"""FASE 5 — Almacenamiento.

1. Copia local en `salida/` (dentro del Codespace: descargable desde el explorador).
2. Subida automática a la nube (OneDrive por defecto) con rclone, si está configurado.
"""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import asdict
from datetime import date
from pathlib import Path

from pilo_studio.config import carpeta_salida
from pilo_studio.models import Guion
from pilo_studio.storage.nube import subir
from pilo_studio.utils import log, slug


def exportar(video: Path, guion: Guion, build: Path, cfg: dict) -> Path:
    raiz = carpeta_salida(cfg)
    if guion.codigo:  # p.ej. salida/FS-001/FS-001.mp4
        base = guion.codigo
        destino = raiz / guion.codigo
    else:
        base = f"{date.today():%Y-%m-%d}_{slug(guion.titulo)}_{guion.formato}"
        destino = raiz / base
    destino.mkdir(parents=True, exist_ok=True)

    final = destino / f"{base}.mp4"
    shutil.copy2(video, final)
    scfg = cfg.get("salida", {})
    if scfg.get("guardar_srt", True) and (build / "subtitulos.srt").exists():
        shutil.copy2(build / "subtitulos.srt", destino / f"{base}.srt")
    if (build / "miniatura.jpg").exists():
        shutil.copy2(build / "miniatura.jpg", destino / f"{base}_miniatura.jpg")
    if scfg.get("guardar_guion", True):
        (destino / "guion.json").write_text(json.dumps(asdict(guion), ensure_ascii=False, indent=2), encoding="utf-8")
    # Metadatos listos para copiar/pegar al subir a YouTube/TikTok/Instagram
    hashtags = " ".join("#" + slug(t).replace("-", "") for t in guion.etiquetas)
    (destino / "publicacion.txt").write_text(
        f"VIDEO:      {base}.mp4\nMINIATURA:  {base}_miniatura.jpg\nSUBTÍTULOS: {base}.srt\n\n"
        f"TÍTULO:\n{guion.titulo}\n\nDESCRIPCIÓN:\n{guion.descripcion}\n\n{hashtags}\n\n"
        f"ETIQUETAS:\n{', '.join(guion.etiquetas)}\n", encoding="utf-8")
    log.info("✅ Exportado a %s", final)
    nube = scfg.get("nube", {}) or {}
    if nube.get("activada", True):
        subir(destino, os.environ.get("PILO_DESTINO_NUBE") or nube.get("destino", ""))
    return final
