from pathlib import Path
import os

ROOT = Path(__file__).resolve().parents[2]
BRANDS_DIR = ROOT / "brands"
SCHEMAS_DIR = ROOT / "schemas"
AGENTS_DIR = ROOT / "pilo_studio" / "agents"
# Carpeta de salida configurable (p. ej. un disco externo): PILO_OUTPUT_DIR=/ruta
OUTPUT_DIR = Path(os.environ.get("PILO_OUTPUT_DIR", ROOT / "output"))
# Imágenes de referencia de personajes/escenas: references/<BRAND>/<CHAR>/*.png
REFERENCES_DIR = Path(os.environ.get("PILO_REFERENCES_DIR", ROOT / "references"))
