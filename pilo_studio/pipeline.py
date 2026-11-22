"""Orquestador del pipeline de Pilo Studio.

    idea + referencias ─► [1 Guion] ─► [2 Lote de imágenes + miniatura] ─► [3 Voz]
                       ─► [4 Montaje + subtítulos] ─► [5 Exportar + subir a OneDrive]

Cada fase guarda su resultado en proyectos/<x>/build/<formato>/, por lo que
una ejecución interrumpida se reanuda sin repetir trabajo (ni llamadas de red).
"""

from __future__ import annotations

import time
from pathlib import Path

from pilo_studio.assembly.montador import montar
from pilo_studio.audio.locutor import generar_audio
from pilo_studio.config import cargar_config
from pilo_studio.director.guionista import escribir_guion
from pilo_studio.models import Guion
from pilo_studio.proyecto import Proyecto
from pilo_studio.storage.exportador import exportar
from pilo_studio.utils import log
from pilo_studio.visuals.estilo import BibliaEstilo
from pilo_studio.visuals.generador import generar_imagenes
from pilo_studio.visuals.miniatura import componer_miniatura

FASES = ["guion", "imagenes", "audio", "montaje", "exportar"]


def producir(ruta_proyecto: Path | str, formato: str = "largo", hasta: str = "exportar",
             regenerar_guion: bool = False, cfg: dict | None = None) -> Path | None:
    proyecto = Proyecto.cargar(ruta_proyecto)
    cfg = cfg or cargar_config(proyecto.ruta)
    if formato not in cfg["formatos"]:
        raise ValueError(f"Formato desconocido '{formato}'. Opciones: {list(cfg['formatos'])}")
    build = proyecto.build(formato)
    biblia = BibliaEstilo(proyecto)
    limite = FASES.index(hasta)
    t0 = time.time()
    log.info("🎬 Pilo Studio · proyecto '%s' · formato %s", proyecto.nombre, formato)

    # 1. Guion
    ruta_guion = build / "guion.json"
    if ruta_guion.exists() and not regenerar_guion:
        guion = Guion.cargar(ruta_guion)
        log.info("[1/5] Guion en caché (%d escenas). Usa --regenerar-guion para rehacerlo.", len(guion.escenas))
    else:
        log.info("[1/5] Escribiendo guion…")
        guion = escribir_guion(proyecto, formato, cfg, biblia)
        guion.guardar(ruta_guion)
    if limite == 0:
        return ruta_guion

    # 2. Imágenes: todas en un solo lote (escenas + fondo de la miniatura)
    log.info("[2/5] Lote de imágenes (semilla de estilo %d)…", biblia.semilla)
    generar_imagenes(guion, build, cfg, biblia)
    componer_miniatura(build / "imagenes" / "miniatura_fondo.png", guion.miniatura_texto or guion.titulo,
                       guion.formato, build / "miniatura.jpg")
    guion.guardar(ruta_guion)
    if limite == 1:
        return build / "imagenes"

    # 3. Voz
    log.info("[3/5] Locución con edge-tts (%s)…", cfg["audio"]["voz"])
    generar_audio(guion, build, cfg)
    guion.guardar(ruta_guion)
    if limite == 2:
        return build / "audio"

    # 4. Montaje
    log.info("[4/5] Ensamblando video y subtítulos…")
    video = montar(guion, build, cfg)
    if limite == 3:
        return video

    # 5. Exportar
    log.info("[5/5] Exportando…")
    final = exportar(video, guion, build, cfg)
    log.info("⏱  Total: %.0f s", time.time() - t0)
    return final
