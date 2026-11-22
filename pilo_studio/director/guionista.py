"""FASE 1 — Dirección y guion.

Convierte la idea del usuario en un `Guion` estructurado por escenas, con
narración exacta y prompts visuales coherentes con la biblia de estilo.

Proveedores, en el orden definido en settings.yaml:
  * manual    -> proyectos/<x>/guion.yaml escrito por el usuario
  * claude    -> API de Anthropic (salida estructurada validada con Pydantic)
  * plantilla -> fallback determinista sin IA (siempre funciona)
"""

from __future__ import annotations

import os
import re

import anthropic
import yaml
from pydantic import BaseModel

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


# ---------------------------------------------------------------- claude
class EscenaIA(BaseModel):
    narracion: str
    prompt_visual: str
    personajes: list[str]
    escenario: str | None


class GuionIA(BaseModel):
    titulo: str
    descripcion: str
    etiquetas: list[str]
    miniatura_texto: str
    miniatura_prompt: str
    escenas: list[EscenaIA]


PROMPT_SISTEMA = """Eres el director creativo y guionista de "Pilo Studio", un canal de YouTube.
Escribes guiones de narración en off claros y emocionantes, con un gancho fuerte en los primeros 5 segundos.
Cada escena corresponde a una sola imagen fija que acompaña a la narración."""

PROMPT_USUARIO = """<idea>
{idea}
</idea>

<universo_visual>
{estilo}
</universo_visual>

Formato: {formato_desc}
- Longitud total de la narración: unas {palabras} palabras, en idioma "{idioma}".
- Entre {escenas_min} y {escenas_max} escenas.
- "narracion": el texto EXACTO que leerá la voz sintética: sin acotaciones, emojis ni indicaciones como [música].
- "prompt_visual": descripción en INGLÉS de la imagen (sujeto, acción, encuadre, iluminación). Usa los
  nombres de personajes y escenarios del universo visual para que el estilo sea consistente.
- "personajes": nombres de los personajes del universo visual que aparecen en la escena (lista vacía si ninguno).
- "escenario": nombre de un escenario del universo visual, o null.
- "descripcion" y "etiquetas": listas para publicar en YouTube (descripción de 2-3 frases, 8-15 etiquetas).
- "miniatura_texto": 2 a 5 palabras MUY llamativas para la miniatura (en el idioma del video, sin emojis).
- "miniatura_prompt": descripción en INGLÉS de una miniatura de YouTube irresistible (primer plano del
  protagonista con emoción intensa, alto contraste, composición simple, espacio libre para el texto, sin texto).
- La última escena cierra con una llamada a la acción breve (suscribirse / seguir)."""


def guion_claude(proyecto: Proyecto, formato: str, cfg: dict, biblia: BibliaEstilo) -> Guion | None:
    if not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
        log.warning("Falta ANTHROPIC_API_KEY (secreto de Codespaces/Actions); se omite Claude.")
        return None
    cc = cfg["guion"]["claude"]
    es_short = formato == "short"
    prompt = PROMPT_USUARIO.format(
        idea=proyecto.idea,
        estilo=biblia.resumen_para_guionista(),
        formato_desc="YouTube Short / Reel vertical de menos de 60 segundos, ritmo rápido" if es_short
        else "Video largo de YouTube (7-10 min) con introducción, desarrollo y cierre",
        palabras=objetivo_palabras(cfg, formato),
        idioma=cfg.get("idioma", "es"),
        escenas_min=4 if es_short else 14,
        escenas_max=7 if es_short else 24,
    )
    cliente = anthropic.Anthropic()
    try:
        r = cliente.beta.messages.parse(
            model=cc.get("modelo", "claude-opus-5-5"),
            max_tokens=16000,
            output_config={"effort": cc.get("esfuerzo", "medium")},
            # Si el modelo declina la petición, la API la reintenta en otro modelo automáticamente
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            system=PROMPT_SISTEMA,
            messages=[{"role": "user", "content": prompt}],
            output_format=GuionIA,
        )
    except anthropic.AuthenticationError:
        log.error("ANTHROPIC_API_KEY inválida.")
        return None
    except anthropic.RateLimitError:
        log.warning("Límite de uso de la API de Claude alcanzado; prueba más tarde.")
        return None
    except anthropic.APIStatusError as e:
        log.warning("Error de la API de Claude (%s): %s", e.status_code, e.message)
        return None
    except anthropic.APIConnectionError:
        log.warning("Sin conexión con la API de Claude.")
        return None
    if r.stop_reason == "refusal" or r.parsed_output is None:
        log.warning("Claude no devolvió un guion (stop_reason=%s).", r.stop_reason)
        return None
    datos = r.parsed_output.model_dump()
    datos["formato"] = formato
    log.info("Claude: %d tokens de entrada, %d de salida", r.usage.input_tokens, r.usage.output_tokens)
    return Guion.desde_dict(datos)


# ---------------------------------------------------------------- plantilla
def _oraciones(texto: str) -> list[str]:
    return [o.strip() for o in re.split(r"(?<=[.!?¡¿])\s+", texto) if o.strip()]


def guion_plantilla(proyecto: Proyecto, formato: str, cfg: dict, biblia: BibliaEstilo) -> Guion:
    """Sin IA: cada párrafo (o grupo de oraciones) de idea.md se vuelve una escena.

    Útil para escribir tú la narración en idea.md y dejar que el sistema
    haga todo lo demás, o como red de seguridad si Claude no está disponible.
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
    return Guion.desde_dict({"titulo": titulo, "formato": formato, "descripcion": cuerpo[:300], "escenas": escenas,
                             "miniatura_texto": " ".join(titulo.split()[:5])})


PROVEEDORES = {"manual": guion_manual, "claude": guion_claude, "plantilla": guion_plantilla}


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
