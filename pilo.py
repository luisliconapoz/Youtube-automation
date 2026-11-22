#!/usr/bin/env python3
"""PILO STUDIO: programa maestro.

Conecta todo el flujo en un solo comando:

    idea ─► Claude (guion) ─► edge-tts (voz) ─► Pollinations/HF (imágenes)
         ─► MoviePy + FFmpeg (video + subtítulos) ─► salida/ + OneDrive (rclone)

Uso:
    python pilo.py                                   # modo guiado (pregunta todo)
    python pilo.py "Por qué el cielo es azul"        # idea directa, formato largo + short
    python pilo.py "idea" --formato short --universo proyectos/ejemplo-pilo-espacio
    python pilo.py --proyecto proyectos/mi-proyecto  # proyecto ya preparado
    python pilo.py --diagnostico                     # revisa el entorno y los secretos
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import shutil
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))

from pilo_studio.pipeline import FASES, producir  # noqa: E402
from pilo_studio.utils import slug  # noqa: E402

log = logging.getLogger("pilo")


# --------------------------------------------------------------------------- diagnóstico
def diagnostico() -> bool:
    """Muestra qué está listo. Devuelve False solo si falta algo imprescindible."""
    def fila(ok: bool, nombre: str, detalle: str) -> None:
        print(f"  {'✅' if ok else '⚠️ '} {nombre:<22} {detalle}")

    print("\n🔎 Diagnóstico de Pilo Studio")
    ffmpeg = bool(shutil.which("ffmpeg"))
    fila(ffmpeg, "FFmpeg", "imprescindible para el montaje" if not ffmpeg else "ok")
    fila(bool(os.environ.get("ANTHROPIC_API_KEY")), "ANTHROPIC_API_KEY",
         "ok: Claude escribirá el guion" if os.environ.get("ANTHROPIC_API_KEY")
         else "falta: se usará el modo plantilla (cada párrafo de la idea = una escena)")
    fila(bool(os.environ.get("POLLINATIONS_API_KEY")), "POLLINATIONS_API_KEY",
         "ok" if os.environ.get("POLLINATIONS_API_KEY") else "opcional: sin ella, ~1 imagen cada 16 s")
    fila(bool(os.environ.get("HF_TOKEN")), "HF_TOKEN",
         "ok: respaldo Hugging Face activo" if os.environ.get("HF_TOKEN") else "opcional: respaldo de imágenes")
    rclone = bool(shutil.which("rclone"))
    conf = bool(os.environ.get("RCLONE_CONF_B64")) or (Path.home() / ".config/rclone/rclone.conf").exists()
    fila(rclone and conf, "OneDrive (rclone)",
         "ok: se subirá automáticamente" if rclone and conf
         else "sin configurar: el video queda en salida/ (ver scripts/conectar_onedrive.sh)")
    print()
    return ffmpeg


# --------------------------------------------------------------------------- proyectos
def crear_proyecto(idea: str, nombre: str | None, universo: Path | None) -> Path:
    if not nombre:  # primera frase de la idea, máximo 8 palabras
        primera = re.split(r"(?<=[.!?])\s|\n", idea.strip(), maxsplit=1)[0]
        nombre = " ".join(primera.split()[:8]).rstrip(".,;:")
    destino = RAIZ / "proyectos" / slug(nombre)
    if destino.exists():
        destino = destino.with_name(f"{destino.name}-{time.strftime('%H%M%S')}")
    origen = universo if universo else RAIZ / "proyectos" / "_plantilla"
    destino.mkdir(parents=True)
    # Reutiliza el "universo" (personajes, estilo, referencias) de otro proyecto
    if (origen / "proyecto.yaml").exists():
        texto = (origen / "proyecto.yaml").read_text(encoding="utf-8")
        lineas = [l if not l.startswith("nombre:") else f"nombre: {nombre}" for l in texto.splitlines()]
        (destino / "proyecto.yaml").write_text("\n".join(lineas) + "\n", encoding="utf-8")
    if (origen / "referencias").exists():
        shutil.copytree(origen / "referencias", destino / "referencias")
    else:
        (destino / "referencias").mkdir()
    (destino / "idea.md").write_text(f"# {nombre}\n\n{idea.strip()}\n", encoding="utf-8")
    log.info("📁 Proyecto creado: %s", destino.relative_to(RAIZ))
    return destino


def preguntar() -> argparse.Namespace:
    print("🎬 PILO STUDIO: modo guiado\n")
    print("Escribe la idea del video (puedes usar varias líneas; termina con una línea vacía):")
    lineas = []
    while True:
        try:
            linea = input("> ")
        except EOFError:
            break
        if not linea.strip() and lineas:
            break
        lineas.append(linea)
    idea = "\n".join(lineas).strip()
    if not idea:
        sys.exit("No escribiste ninguna idea.")
    formato = input("Formato [largo / short / ambos] (Enter = ambos): ").strip().lower() or "ambos"
    if formato not in {"largo", "short", "ambos"}:
        formato = "ambos"
    universos = sorted(p for p in (RAIZ / "proyectos").iterdir()
                       if p.is_dir() and not p.name.startswith("_") and (p / "proyecto.yaml").exists())
    universo = None
    if universos:
        print("¿Reutilizar personajes y estilo de un proyecto existente?")
        print("  0) No, estilo genérico")
        for i, u in enumerate(universos, 1):
            print(f"  {i}) {u.name}")
        op = input("Elige un número (Enter = 0): ").strip()
        if op.isdigit() and 0 < int(op) <= len(universos):
            universo = universos[int(op) - 1]
    return argparse.Namespace(idea=idea, formato=formato, universo=universo, nombre=None,
                              proyecto=None, hasta="exportar", regenerar_guion=False)


# --------------------------------------------------------------------------- main
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Pilo Studio: de una idea a un video publicado.")
    ap.add_argument("idea", nargs="?", help="La idea central del video (entre comillas)")
    ap.add_argument("--formato", choices=["largo", "short", "ambos"], default="ambos")
    ap.add_argument("--proyecto", type=Path, help="Usar un proyecto existente en lugar de una idea nueva")
    ap.add_argument("--universo", type=Path, help="Proyecto del que copiar personajes, estilo y referencias")
    ap.add_argument("--nombre", help="Nombre del proyecto (por defecto, las primeras palabras de la idea)")
    ap.add_argument("--hasta", choices=FASES, default="exportar", help="Detenerse tras esta fase")
    ap.add_argument("--regenerar-guion", action="store_true")
    ap.add_argument("--diagnostico", action="store_true", help="Solo revisar el entorno")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args(argv)

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(message)s", datefmt="%H:%M:%S", stream=sys.stdout)
    for ruidoso in ("urllib3", "httpx", "httpx2", "anthropic"):
        logging.getLogger(ruidoso).setLevel(logging.WARNING)

    if not diagnostico():
        return 1
    if args.diagnostico:
        return 0
    if not args.idea and not args.proyecto:
        args = preguntar()

    proyecto = args.proyecto or crear_proyecto(args.idea, args.nombre, args.universo)
    formatos = ["largo", "short"] if args.formato == "ambos" else [args.formato]
    resultados = {}
    for f in formatos:
        try:
            resultados[f] = producir(proyecto, formato=f, hasta=args.hasta, regenerar_guion=args.regenerar_guion)
        except Exception as e:  # un formato fallido no detiene al otro
            log.exception("❌ Falló el formato %s: %s", f, e)
            resultados[f] = None

    print("\n" + "═" * 60)
    for f, r in resultados.items():
        print(f"  {f:<6} → {r.relative_to(RAIZ) if r and r.is_relative_to(RAIZ) else r or 'ERROR'}")
    print("═" * 60)
    print("Descarga: clic derecho sobre el .mp4 en el explorador → Download.")
    return 0 if all(resultados.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
