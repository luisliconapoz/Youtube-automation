"""FASE 2 — Generación de audio con edge-tts (gratuito, voces neurales).

Además del MP3 de cada escena se capturan los eventos `WordBoundary`, que
dan la marca de tiempo exacta de cada palabra: así los subtítulos quedan
perfectamente sincronizados sin necesidad de transcribir (sin Whisper).
"""

from __future__ import annotations

import asyncio
import json
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
        if datos.get("texto") == escena.narracion:  # caché válida
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

    marcas.write_text(json.dumps({"texto": escena.narracion, "palabras": [p.__dict__ for p in palabras]},
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


async def _listar(idioma: str | None) -> list[dict]:
    voces = await edge_tts.list_voices()
    return [v for v in voces if not idioma or v["Locale"].lower().startswith(idioma.lower())]


def listar_voces(idioma: str | None = None) -> list[dict]:
    return asyncio.run(_listar(idioma))
