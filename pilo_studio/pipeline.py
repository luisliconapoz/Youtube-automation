"""Orquestador del pipeline de Pilo Studio, en 4 pasos:

    [1] Dirección y guion   Claude escribe el guion y los prompts de imagen (neón 2D, personajes oficiales)
    [2] Imágenes ∥ Voz      lote de imágenes (cola paralela) y edge-tts AL MISMO TIEMPO
    [3] Ensamblaje          MoviePy + FFmpeg, subtítulos sincronizados quemados en pantalla
    [4] Exportación         .mp4 + miniatura + .srt + publicacion.txt → salida/ y OneDrive

Cada paso guarda su resultado en proyectos/<x>/build/<formato>/, por lo que
una ejecución interrumpida se reanuda sin repetir trabajo (ni llamadas de red).
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from pilo_studio.assembly.montador import montar
from pilo_studio.audio.locutor import controlar_duracion, generar_audio
from pilo_studio.config import cargar_config
from pilo_studio.director.guionista import escribir_guion
from pilo_studio.models import Guion
from pilo_studio.proyecto import Proyecto
from pilo_studio.storage.exportador import exportar
from pilo_studio.utils import log
from pilo_studio.visuals.estilo import BibliaEstilo
from pilo_studio.visuals.generador import generar_imagenes
from pilo_studio.visuals.miniatura import componer_miniatura

FASES = ["guion", "medios", "montaje", "exportar"]


def producir(ruta_proyecto: Path | str, formato: str = "largo", hasta: str = "exportar",
             regenerar_guion: bool = False, cfg: dict | None = None) -> Path | None:
    proyecto = Proyecto.cargar(ruta_proyecto)
    cfg = cfg or cargar_config(proyecto.ruta)
    if formato not in cfg["formatos"]:
        raise ValueError(f"Formato desconocido '{formato}'. Opciones: {list(cfg['formatos'])}")
    build = proyecto.build(formato)
    biblia = BibliaEstilo(proyecto, cfg)
    limite = FASES.index(hasta)
    t0 = time.time()
    log.info("🎬 Pilo Studio · proyecto '%s' · formato %s", proyecto.nombre, formato)
    if proyecto.provisional:
        log.warning("⚠️  Los personajes de este proyecto son PROVISIONALES (proyecto.yaml → provisional: true). "
                    "Sustitúyelos por los de tu guía oficial para que las imágenes sean fieles.")

    # 1. Dirección y guion
    ruta_guion = build / "guion.json"
    if ruta_guion.exists() and not regenerar_guion:
        guion = Guion.cargar(ruta_guion)
        log.info("[1/4] Guion en caché (%d escenas). Usa --regenerar-guion para rehacerlo.", len(guion.escenas))
    else:
        log.info("[1/4] Dirección y guion…")
        guion = escribir_guion(proyecto, formato, cfg, biblia)
        guion.guardar(ruta_guion)
    if limite == 0:
        return ruta_guion

    # 2. Imágenes (lote) y voz EN PARALELO: son independientes entre sí
    log.info("[2/4] Lote de imágenes ∥ voz con edge-tts (%s)…", cfg["audio"]["voz"])
    with ThreadPoolExecutor(max_workers=1, thread_name_prefix="imagenes") as ex:
        tarea_imagenes = ex.submit(generar_imagenes, guion, build, cfg, biblia)
        generar_audio(guion, build, cfg)          # asyncio en el hilo principal
        controlar_duracion(guion, build, cfg)     # Shorts: 40-60 s garantizados
        tarea_imagenes.result()                   # propaga cualquier error del lote
    mcfg = cfg.get("miniatura", {}) or {}
    texto = (guion.miniatura_texto or guion.titulo) if mcfg.get("titular", True) else ""
    componer_miniatura(build / "imagenes" / "miniatura_fondo.png", texto, guion.formato, build / "miniatura.jpg")
    guion.guardar(ruta_guion)
    if limite == 1:
        return build

    # 3. Ensamblaje y subtítulos
    log.info("[3/4] Ensamblando video y subtítulos…")
    video = montar(guion, build, cfg)
    if limite == 2:
        return video

    # 4. Exportación
    log.info("[4/4] Exportando…")
    final = exportar(video, guion, build, cfg)
    log.info("⏱  Total: %.0f s", time.time() - t0)
    return final
