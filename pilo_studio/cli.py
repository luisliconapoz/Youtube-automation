"""Interfaz de línea de comandos.

    python -m pilo_studio nuevo "Mi idea"            # crea proyectos/mi-idea/
    python -m pilo_studio producir proyectos/mi-idea --formato ambos
    python -m pilo_studio voces --idioma es
"""

from __future__ import annotations

import argparse
import logging
import shutil
import sys

from pilo_studio.config import RAIZ
from pilo_studio.pipeline import FASES, producir
from pilo_studio.utils import slug


def _nuevo(args) -> int:
    destino = RAIZ / "proyectos" / slug(args.nombre)
    if destino.exists():
        print(f"Ya existe: {destino}")
        return 1
    shutil.copytree(RAIZ / "proyectos" / "_plantilla", destino)
    (destino / "idea.md").write_text(f"# {args.nombre}\n\n{args.idea or 'Describe aquí la idea del video.'}\n",
                                     encoding="utf-8")
    print(f"Proyecto creado en {destino}\n"
          f"  1) Edita idea.md  2) Pon imágenes en referencias/  3) Ajusta proyecto.yaml\n"
          f"  4) python -m pilo_studio producir {destino.relative_to(RAIZ)} --formato ambos")
    return 0


def _producir(args) -> int:
    formatos = ["largo", "short"] if args.formato == "ambos" else [args.formato]
    for f in formatos:
        res = producir(args.proyecto, formato=f, hasta=args.hasta, regenerar_guion=args.regenerar_guion)
        print(f"→ {res}")
    return 0


def _voces(args) -> int:
    from pilo_studio.audio.locutor import listar_voces

    for v in listar_voces(args.idioma):
        print(f"{v['ShortName']:<36} {v['Gender']:<7} {v['Locale']}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="pilo_studio", description="Pilo Studio — fábrica de videos a costo cero")
    ap.add_argument("-v", "--verbose", action="store_true")
    sub = ap.add_subparsers(dest="cmd", required=True)

    n = sub.add_parser("nuevo", help="Crear un proyecto desde la plantilla")
    n.add_argument("nombre")
    n.add_argument("--idea", default="")
    n.set_defaults(fn=_nuevo)

    p = sub.add_parser("producir", help="Ejecutar el pipeline completo")
    p.add_argument("proyecto")
    p.add_argument("--formato", choices=["largo", "short", "ambos"], default="largo")
    p.add_argument("--hasta", choices=FASES, default="exportar", help="Detenerse tras esta fase (p.ej. revisar guion)")
    p.add_argument("--regenerar-guion", action="store_true")
    p.set_defaults(fn=_producir)

    v = sub.add_parser("voces", help="Listar voces de edge-tts")
    v.add_argument("--idioma", default="es")
    v.set_defaults(fn=_voces)

    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)-7s %(message)s", datefmt="%H:%M:%S",
                        stream=sys.stdout)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    return args.fn(args)
