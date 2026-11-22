"""FASE 1 — Dirección y guion.

Convierte la idea del usuario en un `Guion` estructurado por escenas, con
narración exacta y prompts visuales coherentes con la biblia de estilo.

Proveedores (costo cero), en el orden definido en settings.yaml:
  * manual    -> proyectos/<x>/guion.yaml escrito por el usuario
  * ollama    -> LLM local open-source (llama3.1, qwen2.5, mistral…)
  * plantilla -> fallback determinista sin IA (siempre funciona)
"""

from __future__ import annotations

import json
import re

import requests
import yaml

from pilo_studio.models import Guion
from pilo_studio.proyecto import Proyecto
from pilo_studio.utils import log
from pilo_studio.visuals.estilo import BibliaEstilo

PALABRAS_POR_MINUTO = 150  # ritmo natural de locución en español


def objetivo_palabras(cfg: dict, formato: str) -> int:
    return int(cfg["formatos"][formato]["duracion_objetivo_min"] * PALABRAS_POR_MINUTO)


# ---------------------------------------------------------------- manual
def guion_manual(proyecto: Proyecto, formato: str, cfg: dict, biblia: BibliaEstilo) -> Guion | None:
    if not proyecto.guion_manual.exists():
        return None
    datos = yaml.safe_load(proyecto.guion_manual.read_text(encoding="utf-8")) or {}
    # Permite un guion.yaml con claves por formato: {largo: {...}, short: {...}}
    if formato in datos and isinstance(datos[formato], dict):
        datos = datos[formato]
    elif "escenas" not in datos:
        return None
    datos.setdefault("formato", formato)
    return Guion.desde_dict(datos)


# ---------------------------------------------------------------- ollama
PROMPT_SISTEMA = """Eres el director creativo y guionista de "Pilo Studio", un canal de YouTube.
Escribes guiones de narración en off, claros, emocionantes y con un gancho fuerte en los primeros 5 segundos.
Respondes ÚNICAMENTE con JSON válido, sin comentarios ni markdown."""

PROMPT_USUARIO = """IDEA CENTRAL:
{idea}

UNIVERSO VISUAL (respétalo en cada prompt visual):
{estilo}

FORMATO: {formato_desc}
- Longitud total de la narración: ~{palabras} palabras (idioma: {idioma}).
- Divide en {escenas_min}-{escenas_max} escenas. Cada escena = una sola imagen.
- "narracion": texto EXACTO que leerá la voz. Sin acotaciones, sin emojis, sin "[música]".
- "prompt_visual": descripción en INGLÉS de la imagen (sujeto, acción, encuadre, iluminación).
  Usa los nombres de personajes/escenarios definidos para mantener consistencia.
- "personajes": lista de nombres de personajes que aparecen. "escenario": nombre del escenario o null.
- Termina con una llamada a la acción breve (suscribirse / seguir).

Devuelve exactamente este esquema:
{{"titulo": str, "descripcion": str, "etiquetas": [str],
  "escenas": [{{"narracion": str, "prompt_visual": str, "personajes": [str], "escenario": str|null}}]}}"""


def _extraer_json(texto: str) -> dict:
    texto = texto.strip()
    try:
        return json.loads(texto)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", texto, re.S)
        if not m:
            raise
        return json.loads(m.group(0))


def guion_ollama(proyecto: Proyecto, formato: str, cfg: dict, biblia: BibliaEstilo) -> Guion | None:
    oc = cfg["guion"]["ollama"]
    palabras = objetivo_palabras(cfg, formato)
    es_short = formato == "short"
    prompt = PROMPT_USUARIO.format(
        idea=proyecto.idea,
        estilo=biblia.resumen_para_guionista(),
        formato_desc="YouTube Short / Reel vertical (<60 s), ritmo rápido" if es_short
        else "Video largo de YouTube (7-10 min), narrativa con introducción, desarrollo y cierre",
        palabras=palabras,
        idioma=cfg.get("idioma", "es"),
        escenas_min=5 if es_short else 14,
        escenas_max=8 if es_short else 24,
    )
    try:
        r = requests.post(
            f"{oc['url'].rstrip('/')}/api/generate",
            json={
                "model": oc["modelo"],
                "system": PROMPT_SISTEMA,
                "prompt": prompt,
                "format": "json",
                "stream": False,
                "options": {"temperature": oc.get("temperatura", 0.8), "num_ctx": 8192},
            },
            timeout=oc.get("timeout", 600),
        )
        r.raise_for_status()
    except requests.RequestException as e:
        log.warning("Ollama no disponible (%s). Instálalo gratis en https://ollama.com", e)
        return None
    datos = _extraer_json(r.json()["response"])
    datos["formato"] = formato
    guion = Guion.desde_dict(datos)
    if not guion.escenas:
        log.warning("Ollama devolvió un guion vacío.")
        return None
    return guion


# ---------------------------------------------------------------- plantilla
def _oraciones(texto: str) -> list[str]:
    return [o.strip() for o in re.split(r"(?<=[.!?¡¿])\s+", texto) if o.strip()]


def guion_plantilla(proyecto: Proyecto, formato: str, cfg: dict, biblia: BibliaEstilo) -> Guion:
    """Sin IA: cada párrafo (o grupo de oraciones) de idea.md se vuelve una escena.

    Útil para escribir tú la narración en idea.md y dejar que el sistema
    haga todo lo demás, o como red de seguridad si no hay LLM.
    """
    lineas = proyecto.idea.splitlines()
    titulo = proyecto.nombre
    if lineas and lineas[0].startswith("#"):
        titulo = lineas[0].lstrip("# ").strip()
        lineas = lineas[1:]
    cuerpo = "\n".join(lineas).strip()
    parrafos = [p.strip().replace("\n", " ") for p in re.split(r"\n\s*\n", cuerpo) if p.strip()]
    max_palabras = 35 if formato == "short" else 70
    bloques: list[str] = []
    for p in parrafos:
        actual: list[str] = []
        for o in _oraciones(p):
            if actual and len(" ".join(actual + [o]).split()) > max_palabras:
                bloques.append(" ".join(actual))
                actual = []
            actual.append(o)
        if actual:
            bloques.append(" ".join(actual))
    # Recortar al presupuesto de palabras del formato (p.ej. Shorts < 60 s)
    limite = int(objetivo_palabras(cfg, formato) * 1.15)
    recortados, total = [], 0
    for b in bloques:
        n = len(b.split())
        if recortados and total + n > limite:
            break
        recortados.append(b)
        total += n
    if formato == "short" and len(bloques) > len(recortados) and bloques[-1] not in recortados:
        recortados[-1] = bloques[-1]  # conservar el cierre / llamada a la acción
    bloques = recortados
    nombres = list(biblia.estilo.personajes)
    escenas = []
    for b in bloques:
        presentes = [n for n in nombres if n.lower() in b.lower()]
        escenas.append({"narracion": b, "prompt_visual": f"cinematic illustration of: {b}", "personajes": presentes})
    return Guion.desde_dict({"titulo": titulo, "formato": formato, "descripcion": cuerpo[:300], "escenas": escenas})


PROVEEDORES = {"manual": guion_manual, "ollama": guion_ollama, "plantilla": guion_plantilla}


def escribir_guion(proyecto: Proyecto, formato: str, cfg: dict, biblia: BibliaEstilo) -> Guion:
    for nombre in cfg["guion"]["proveedores"]:
        fn = PROVEEDORES.get(nombre)
        if fn is None:
            log.warning("Proveedor de guion desconocido: %s", nombre)
            continue
        guion = fn(proyecto, formato, cfg, biblia)
        if guion and guion.escenas:
            log.info("Guion '%s' vía %s: %d escenas, %d palabras (~%.1f min)",
                     guion.titulo, nombre, len(guion.escenas), guion.total_palabras,
                     guion.total_palabras / PALABRAS_POR_MINUTO)
            return guion
    raise RuntimeError("Ningún proveedor de guion produjo resultado.")
