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
from typing import Literal

import anthropic
import yaml
from pydantic import BaseModel, Field, create_model

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
def modelo_guion(biblia: BibliaEstilo) -> type[BaseModel]:
    """Esquema de salida construido a partir del universo del proyecto.

    Los nombres de personaje y las expresiones son enumeraciones cerradas: Claude
    SOLO puede usar los personajes oficiales y las expresiones permitidas.
    """
    nombres = biblia.nombres_personajes
    TipoPersonaje = Literal[tuple(nombres)] if nombres else str  # type: ignore[valid-type]
    TipoExpresion = Literal[tuple(biblia.expresiones)] if biblia.expresiones else str  # type: ignore[valid-type]
    Aparicion = create_model(
        "Aparicion",
        personaje=(TipoPersonaje, ...),
        expresion=(TipoExpresion, ...),
        pose=(str, Field(..., description="Pose corporal concreta en inglés")),
    )
    EscenaIA = create_model(
        "EscenaIA",
        narracion=(str, ...),
        prompt_visual=(str, Field(..., description="Prompt de imagen detallado en inglés, sin texto ni cifras")),
        reparto=(list[Aparicion], ...),
        escenario=(str | None, ...),
    )
    return create_model(
        "GuionIA",
        titulo=(str, ...),
        descripcion=(str, ...),
        etiquetas=(list[str], ...),
        miniatura_texto=(str, ...),
        miniatura_prompt=(str, ...),
        escenas=(list[EscenaIA], ...),
    )


PROMPT_SISTEMA = """Eres el director creativo y guionista de "Pilo Studio", un canal de YouTube de divulgación.
Escribes guiones de narración en off claros y emocionantes, con un gancho fuerte en los primeros 5 segundos,
y diriges el arte de cada escena: cada escena es UNA ilustración fija, numerada en secuencia
(Image 001, Image 002, …), que acompaña a la narración.

Reglas de dirección de arte, obligatorias en todas las escenas:
1. Estilo: ilustración vectorial minimalista en estilo neón 2D sobre fondo negro puro, limpia y profesional.
   Nada de renders 3D, fotos ni texturas realistas. Nada de animaciones básicas ni imágenes genéricas.
2. Personajes: usa ÚNICAMENTE los personajes oficiales del universo, cada uno en su rol y con sus colores
   oficiales. No inventes personajes nuevos. Si una escena no necesita personajes, usa objetos o escenarios
   simbólicos del mismo estilo.
3. Expresión y pose: a cada personaje que aparece asígnale la expresión que corresponde lógicamente a lo que
   se dice (Talking cuando explica, Thinking cuando duda, Happy cuando gana, etc.) y una pose corporal concreta,
   corporativa o dinámica, coherente con la acción.
4. PROHIBIDO ABSOLUTO dentro de las imágenes: texto, títulos, letras, palabras, números, cifras, símbolos de
   moneda con cantidades, carteles legibles, marcas de agua y logos. Para expresar cantidades usa metáforas
   visuales (pilas de monedas más altas o más bajas, flechas, gráficos sin ejes ni etiquetas).
5. Continuidad: las imágenes forman una secuencia; mantén coherencia de personajes, colores y escenario de una
   escena a la siguiente, y varía el encuadre (plano general, medio, primer plano) para dar ritmo."""

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
- "prompt_visual": prompt de imagen detallado en INGLÉS (40-90 palabras) que describa: encuadre ({encuadre}),
  composición, acción principal, objetos simbólicos, colores neón dominantes e iluminación (brillo neón sobre
  negro). No repitas aquí el aspecto de los personajes: se añade automáticamente desde su ficha oficial.
  Sin texto, sin números, sin nada entre comillas.
- "reparto": un elemento por personaje oficial presente, con su "expresion" (de la lista permitida) y una "pose"
  corporal concreta en inglés. Lista vacía si no aparece ningún personaje.
- "escenario": nombre de un escenario del universo visual, o null.
- "descripcion" y "etiquetas": para publicar en YouTube (descripción de 2-3 frases, 8-15 etiquetas).
- "miniatura_texto": 2 a 5 palabras MUY llamativas para la miniatura (en el idioma del video, sin emojis).
- "miniatura_prompt": prompt en INGLÉS para el fondo de la miniatura, en el mismo estilo neón 2D: primer plano
  del personaje protagonista con expresión intensa, alto contraste, composición simple y un lado despejado
  para el titular (que se añade después: la imagen en sí NO lleva texto).
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
        encuadre="vertical 9:16" if es_short else "16:9 widescreen",
    )
    cliente = anthropic.Anthropic()
    try:
        # Streaming: un guion largo con prompts detallados puede ser extenso
        with cliente.beta.messages.stream(
            model=cc.get("modelo", "claude-opus-5-5"),
            max_tokens=64000,
            output_config={"effort": cc.get("esfuerzo", "medium")},
            # Si el modelo declina la petición, la API la reintenta en otro modelo automáticamente
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            system=PROMPT_SISTEMA,
            messages=[{"role": "user", "content": prompt}],
            output_format=modelo_guion(biblia),
        ) as stream:
            r = stream.get_final_message()
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
        escenas.append({
            "narracion": b,
            "prompt_visual": f"symbolic neon scene illustrating: {b}",
            "reparto": [{"personaje": n, "expresion": "Talking", "pose": "presenting with an open palm"}
                        for n in presentes],
        })
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
