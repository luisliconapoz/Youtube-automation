"""FASE 4 — Ensamblaje: MoviePy compone, FFmpeg quema subtítulos y mezcla música.

1. MoviePy: una toma por escena (imagen + Ken Burns) sincronizada con su locución.
2. FFmpeg (libass): subtítulos .ass incrustados + música de fondo opcional en
   una sola pasada de codificación final.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
from moviepy import AudioFileClip, CompositeAudioClip, VideoClip, concatenate_videoclips
from PIL import Image

from pilo_studio.assembly.subtitulos import construir_lineas, escribir_ass, escribir_srt
from pilo_studio.config import RAIZ
from pilo_studio.models import Escena, Guion
from pilo_studio.utils import ejecutar, ffmpeg_bin, log


def _toma(escena: Escena, duracion: float, ancho: int, alto: int, vcfg: dict) -> VideoClip:
    """Clip de una escena con movimiento de cámara suave (Ken Burns)."""
    zmax = float(vcfg.get("zoom_max", 1.12)) if vcfg.get("ken_burns", True) else 1.0
    base = Image.open(escena.imagen).convert("RGB")
    base = base.resize((math.ceil(ancho * zmax), math.ceil(alto * zmax)), Image.Resampling.LANCZOS)
    bw, bh = base.size
    acercar = escena.id % 2 == 1          # alterna zoom-in / zoom-out
    deriva = 1 if escena.id % 4 < 2 else -1  # alterna dirección del paneo

    if zmax == 1.0:
        cuadro = np.asarray(base)
        return VideoClip(lambda t: cuadro, duration=duracion)

    def cuadro(t: float) -> np.ndarray:
        p = min(max(t / duracion, 0.0), 1.0)
        p = p * p * (3 - 2 * p)  # easing suave
        z = 1 + (zmax - 1) * (p if acercar else 1 - p)
        w, h = bw / z, bh / z
        cx = bw / 2 + deriva * (bw - w) / 2 * (p - 0.5)
        cy = bh / 2
        caja = (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)
        return np.asarray(base.resize((ancho, alto), Image.Resampling.BILINEAR, box=caja))

    return VideoClip(cuadro, duration=duracion)


def montar(guion: Guion, build: Path, cfg: dict) -> Path:
    fmt = cfg["formatos"][guion.formato]
    vcfg = cfg["video"]
    ancho, alto, fps = fmt["ancho"], fmt["alto"], vcfg.get("fps", 30)
    pausa = float(fmt.get("pausa_entre_escenas", vcfg.get("pausa_entre_escenas", 0.35)))

    # ---- 1) Composición con MoviePy
    tomas, pistas, t = [], [], 0.0
    for e in guion.escenas:
        dur = (e.duracion or 0) + pausa
        tomas.append(_toma(e, dur, ancho, alto, vcfg))
        pistas.append(AudioFileClip(e.audio).with_start(t))
        t += dur
    video = concatenate_videoclips(tomas, method="chain")
    video = video.with_audio(CompositeAudioClip(pistas).with_duration(t))
    borrador = build / "borrador.mp4"
    log.info("Renderizando %d escenas (%.1f s, %dx%d @%dfps)…", len(tomas), t, ancho, alto, fps)
    video.write_videofile(str(borrador), fps=fps, codec="libx264", audio_codec="aac",
                          preset="ultrafast", ffmpeg_params=["-crf", "16"], logger=None)
    video.close()
    for p in pistas:
        p.close()

    # ---- 2) Subtítulos
    lineas = construir_lineas(guion, fmt["palabras_por_subtitulo"], pausa)
    escribir_srt(lineas, build / "subtitulos.srt")
    scfg = vcfg.get("subtitulos", {})
    escribir_ass(lineas, build / "subtitulos.ass", ancho, alto, fmt, scfg)

    # ---- 3) Pasada final FFmpeg: subtítulos + música + codificación de entrega
    final = build / "final.mp4"
    cmd = [ffmpeg_bin(), "-y", "-i", borrador.name]
    musica = (vcfg.get("musica") or {}).get("archivo")
    ruta_musica = (RAIZ / musica) if musica and not Path(musica).is_absolute() else (Path(musica) if musica else None)
    if ruta_musica and ruta_musica.exists():
        vol = (vcfg.get("musica") or {}).get("volumen", 0.08)
        cmd += ["-stream_loop", "-1", "-i", str(ruta_musica),
                "-filter_complex", f"[1:a]volume={vol}[m];[0:a][m]amix=inputs=2:duration=first:normalize=0[a]",
                "-map", "0:v", "-map", "[a]"]
    if scfg.get("activados", True):
        cmd += ["-vf", "ass=subtitulos.ass"]  # ruta relativa: evita problemas de escape en Windows
    cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", final.name]
    ejecutar(cmd, cwd=build)
    log.info("Video ensamblado: %s", final)
    return final

