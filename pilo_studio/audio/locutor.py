"""FASE 2 — Generación de audio con edge-tts (gratuito, voces neurales).

Además del MP3 de cada escena se capturan los eventos `WordBoundary`, que
dan la marca de tiempo exacta de cada palabra: así los subtítulos quedan
perfectamente sincronizados sin necesidad de transcribir (sin Whisper).
"""

from __future__ import annotations

import asyncio
import json
import math
from pathlib import Path

import edge_tts

from pilo_studio.models import Escena, Guion, Palabra
from pilo_studio.utils import duracion_media, log

TICKS = 10_000_000  # edge-tts usa unidades de 100 ns


async def _sintetizar(escena: Escena, destino: Path, acfg: dict) -> None:
    mp3 = destino / f"escena_{escena.id:03d}.mp3"
    marcas = destino / f"escena_{escena.id:03d}.json"
    if mp3.exists() and marcas.exists() and mp3.stat().st_size > 0:
        datos = json.loads(marcas.read_text(encoding="utf-8"))
        # caché válida solo si coinciden el texto, la voz y la velocidad
        if (datos.get("texto"), datos.get("voz", acfg["voz"]), datos.get("velocidad", "+0%")) == \
                (escena.narracion, acfg["voz"], acfg.get("velocidad", "+0%")):
            escena.audio, escena.palabras = str(mp3), [Palabra(**p) for p in datos["palabras"]]
            escena.duracion = duracion_media(mp3)
            return

    for intento in range(1, acfg.get("reintentos", 3) + 1):
        try:
            com = edge_tts.Communicate(
                escena.narracion,
                acfg["voz"],
                rate=acfg.get("velocidad", "+0%"),
                pitch=acfg.get("tono", "+0Hz"),
                volume=acfg.get("volumen", "+0%"),
                boundary="WordBoundary",
            )
            palabras: list[Palabra] = []
            with open(mp3, "wb") as f:
                async for chunk in com.stream():
                    if chunk["type"] == "audio":
                        f.write(chunk["data"])
                    elif chunk["type"] == "WordBoundary":
                        ini = chunk["offset"] / TICKS
                        palabras.append(Palabra(chunk["text"], ini, ini + chunk["duration"] / TICKS))
            break
        except Exception as e:  # red inestable, rate limit…
            log.warning("TTS escena %d intento %d falló: %s", escena.id, intento, e)
            if intento == acfg.get("reintentos", 3):
                raise
            await asyncio.sleep(2 * intento)

    marcas.write_text(json.dumps({"texto": escena.narracion, "voz": acfg["voz"],
                                  "velocidad": acfg.get("velocidad", "+0%"),
                                  "palabras": [p.__dict__ for p in palabras]},
                                 ensure_ascii=False), encoding="utf-8")
    escena.audio, escena.palabras = str(mp3), palabras
    escena.duracion = duracion_media(mp3)
    log.info("  🎙  escena %d: %.1fs", escena.id, escena.duracion)


async def _todas(guion: Guion, destino: Path, acfg: dict) -> None:
    sem = asyncio.Semaphore(acfg.get("concurrencia", 4))

    async def una(e: Escena):
        async with sem:
            await _sintetizar(e, destino, acfg)

    await asyncio.gather(*(una(e) for e in guion.escenas))


def generar_audio(guion: Guion, build: Path, cfg: dict) -> Guion:
    destino = build / "audio"
    destino.mkdir(parents=True, exist_ok=True)
    asyncio.run(_todas(guion, destino, cfg["audio"]))
    total = sum(e.duracion or 0 for e in guion.escenas)
    log.info("Audio listo: %d escenas, %.1f s en total", len(guion.escenas), total)
    return guion


def _porcentaje(v: str) -> int:
    return int(str(v).strip().rstrip("%") or 0)


def duracion_total(guion: Guion, pausa: float) -> float:
    return sum((e.duracion or 0) + pausa for e in guion.escenas)


def controlar_duracion(guion: Guion, build: Path, cfg: dict) -> Guion:
    """Garantiza la duración del formato (Shorts: 40-60 s).

    Si la locución se pasa del máximo, se vuelve a sintetizar más rápida (la
    duración escala ~1/velocidad). Si se queda corta, se avisa.
    """
    fmt = cfg["formatos"][guion.formato]
    maximo, minimo = fmt.get("duracion_max_s"), fmt.get("duracion_min_s")
    if not maximo and not minimo:
        return guion
    pausa = float(fmt.get("pausa_entre_escenas", cfg["video"].get("pausa_entre_escenas", 0.35)))
    total = duracion_total(guion, pausa)
    if maximo and total > maximo:
        actual = _porcentaje(cfg["audio"].get("velocidad", "+0%"))
        fijo = pausa * len(guion.escenas)
        nuevo = math.ceil(((1 + actual / 100) * (total - fijo) / (maximo - fijo - 0.5) - 1) * 100)
        tope = int(cfg["audio"].get("velocidad_max", 25))
        if nuevo > tope:
            log.warning("La narración es demasiado larga incluso a +%d%%; acorta el guion.", tope)
            nuevo = tope
        log.info("  ⏩ %.1f s > %d s: re-sintetizando la voz a %+d%%", total, maximo, nuevo)
        generar_audio(guion, build, {**cfg, "audio": {**cfg["audio"], "velocidad": f"{nuevo:+d}%"}})
        total = duracion_total(guion, pausa)
    if minimo and total < minimo:
        log.warning("  ⚠️  El video dura %.1f s (mínimo %d s): el guion quedó corto.", total, minimo)
    log.info("  ⏱  Duración final de la locución: %.1f s", total)
    return guion


async def _listar(idioma: str | None) -> list[dict]:
    voces = await edge_tts.list_voices()
    return [v for v in voces if not idioma or v["Locale"].lower().startswith(idioma.lower())]


def listar_voces(idioma: str | None = None) -> list[dict]:
    return asyncio.run(_listar(idioma))
