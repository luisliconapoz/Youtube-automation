#!/usr/bin/env python3
"""PILO STUDIO: programa maestro.

Conecta todo el flujo en un solo comando:

    [1] canal + idea ─► Claude (guion + prompts neón 2D con la guía oficial del canal)
    [2] lote de imágenes (Pollinations/HF en paralelo)  ∥  voz edge-tts (40-60 s garantizados)
    [3] MoviePy + FFmpeg (video 9:16 + subtítulos quemados)
    [4] salida/ + OneDrive: .mp4, miniatura, .srt y publicacion.txt

Uso:
    python pilo.py                                   # modo guiado (canal, idea, formato)
    python pilo.py "Cómo funciona el interés compuesto" --canal fact-stick
    python pilo.py "Cómo gana dinero Costco" --canal wild-money
    python pilo.py "Rentar o comprar casa" --canal money-lab --formato largo
    python pilo.py "idea" --sin-universo             # sin personajes oficiales
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

from pilo_studio.config import cargar_config  # noqa: E402
from pilo_studio.pipeline import FASES, producir  # noqa: E402
from pilo_studio.proyecto import Proyecto  # noqa: E402
from pilo_studio.utils import slug  # noqa: E402

log = logging.getLogger("pilo")


# --------------------------------------------------------------------------- universo
def universo_por_defecto() -> Path | None:
    ruta = cargar_config().get("universo_por_defecto")
    if not ruta:
        return None
    ruta = Path(ruta) if Path(ruta).is_absolute() else RAIZ / ruta
    return ruta if (ruta / "proyecto.yaml").exists() else None


def canales() -> list[Path]:
    """Proyectos marcados como `canal: true` (universos oficiales con guía)."""
    return sorted(p for p in (RAIZ / "proyectos").iterdir()
                  if p.is_dir() and (p / "proyecto.yaml").exists() and Proyecto.cargar_meta(p)["canal"])


def ruta_canal(nombre: str) -> Path:
    ruta = RAIZ / "proyectos" / slug(nombre)
    if not (ruta / "proyecto.yaml").exists():
        disponibles = ", ".join(c.name for c in canales())
        sys.exit(f"No existe el canal '{nombre}'. Disponibles: {disponibles}")
    return ruta


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
    for c in canales():
        u = Proyecto.cargar_meta(c)
        guia = "con guía oficial" if (c / "guia").exists() and any((c / "guia").iterdir()) else "SIN guía"
        fila(not u["provisional"], f"Canal {c.name}",
             f"{', '.join(u['personajes'])} · {guia}" + ("  ← PROVISIONAL" if u["provisional"] else ""))
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
        lineas = []
        for l in texto.splitlines():
            if l.startswith("nombre:"):
                l = f"nombre: {nombre}"
            elif l.startswith("canal:"):  # el video hereda el universo, pero no es un canal
                l = f"canal: false\ncanal_origen: {origen.name}"
            lineas.append(l)
        (destino / "proyecto.yaml").write_text("\n".join(lineas) + "\n", encoding="utf-8")
    for carpeta in ("referencias", "guia"):
        if (origen / carpeta).exists():
            shutil.copytree(origen / carpeta, destino / carpeta)
    (destino / "referencias").mkdir(exist_ok=True)
    (destino / "idea.md").write_text(f"# {nombre}\n\n{idea.strip()}\n", encoding="utf-8")
    log.info("📁 Proyecto creado: %s", destino.relative_to(RAIZ))
    return destino


def preguntar() -> argparse.Namespace:
    print("🎬 PILO STUDIO: modo guiado\n")
    lista = canales()
    defecto = universo_por_defecto()
    universo = defecto
    if lista:
        print("¿Para qué canal es el video?")
        for i, c in enumerate(lista, 1):
            m = Proyecto.cargar_meta(c)
            print(f"  {i}) {m['nombre']:<12} {m['nicho']}{'  (por defecto)' if c == defecto else ''}")
        print("  0) Ninguno (sin personajes oficiales)")
        op = input("Elige un número (Enter = por defecto): ").strip()
        if op == "0":
            universo = None
        elif op.isdigit() and 0 < int(op) <= len(lista):
            universo = lista[int(op) - 1]
    print("\nEscribe la idea o el tema del video (varias líneas; termina con una línea vacía):")
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
    formato = input("Formato [short / largo / ambos] (Enter = short 9:16 de 40-60 s): ").strip().lower() or "short"
    if formato not in {"largo", "short", "ambos"}:
        formato = "short"
    return argparse.Namespace(idea=idea, formato=formato, universo=universo, nombre=None,
                              proyecto=None, hasta="exportar", regenerar_guion=False)


# --------------------------------------------------------------------------- resumen
def _rel(p: Path) -> str:
    return str(p.relative_to(RAIZ)) if p.is_relative_to(RAIZ) else str(p)


def resumen(resultados: dict[str, Path | None]) -> None:
    print("\n" + "═" * 64)
    print("  🎬 LISTO PARA REVISAR Y SUBIR")
    print("═" * 64)
    for f, r in resultados.items():
        if r is None:
            print(f"  {f.upper()}: ❌ error (revisa el registro de arriba)")
            continue
        if r.suffix != ".mp4":  # se detuvo antes de exportar (--hasta)
            print(f"  {f.upper()}: {_rel(r)}")
            continue
        carpeta = r.parent
        print(f"  {f.upper()}  ·  {_rel(carpeta)}/")
        for nombre, patron in [("Video", "*.mp4"), ("Miniatura", "*_miniatura.jpg"),
                               ("Subtítulos", "*.srt"), ("Título y descripción", "publicacion.txt")]:
            encontrados = sorted(carpeta.glob(patron))
            print(f"     {'✅' if encontrados else '—'} {nombre:<21} {encontrados[0].name if encontrados else ''}")
    print("═" * 64)
    print("  Descargar al iPad: pulsación larga sobre el archivo en el explorador → Download.")
    print("  Si OneDrive está conectado, todo está también en OneDrive/PiloStudio/Videos/.")


# --------------------------------------------------------------------------- main
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Pilo Studio: de una idea a un video publicado.")
    ap.add_argument("idea", nargs="?", help="La idea central del video (entre comillas)")
    ap.add_argument("--formato", choices=["largo", "short", "ambos"], default="short",
                    help="short = 9:16 de 40-60 s (por defecto)")
    ap.add_argument("--canal", help="fact-stick | money-lab | wild-money (por defecto: universo_por_defecto)")
    ap.add_argument("--proyecto", type=Path, help="Usar un proyecto existente en lugar de una idea nueva")
    ap.add_argument("--universo", type=Path,
                    help="Proyecto del que copiar personajes, estilo y referencias (por defecto: universo_por_defecto)")
    ap.add_argument("--sin-universo", action="store_true", help="No usar el universo de personajes por defecto")
    ap.add_argument("--nombre", help="Nombre del proyecto (por defecto, las primeras palabras de la idea)")
    ap.add_argument("--hasta", choices=FASES, default="exportar",
                    help="Detenerse tras este paso: guion | medios (imágenes+voz) | montaje | exportar")
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
    elif getattr(args, "canal", None):
        args.universo = ruta_canal(args.canal)
    elif not args.proyecto and not args.universo and not getattr(args, "sin_universo", False):
        args.universo = universo_por_defecto()

    proyecto = args.proyecto or crear_proyecto(args.idea, args.nombre, args.universo)
    formatos = ["largo", "short"] if args.formato == "ambos" else [args.formato]
    resultados = {}
    for f in formatos:
        try:
            resultados[f] = producir(proyecto, formato=f, hasta=args.hasta, regenerar_guion=args.regenerar_guion)
        except Exception as e:  # un formato fallido no detiene al otro
            log.exception("❌ Falló el formato %s: %s", f, e)
            resultados[f] = None

    resumen(resultados)
    return 0 if all(resultados.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
