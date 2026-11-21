"""Especificaciones de formato (LARGO / SHORT) y regla de decisión de formato.

Bloque 1: criterios para decidir si una idea conviene como video largo o Short.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class FormatSpec:
    name: str
    aspect: str
    width: int
    height: int
    min_seconds: int
    max_seconds: int
    target_min_seconds: int
    target_max_seconds: int
    words_per_minute: int          # ritmo de locución objetivo
    scene_min_seconds: float       # duración mínima de una imagen en pantalla
    scene_max_seconds: float       # duración máxima antes de cambiar de imagen
    hook_max_seconds: float        # el hook debe resolverse antes de este segundo
    rehook_every_seconds: int      # cada cuánto debe haber un re-hook / cambio de patrón


LONG = FormatSpec(
    name="LONG", aspect="16:9", width=1920, height=1080,
    min_seconds=7 * 60, max_seconds=15 * 60,
    target_min_seconds=8 * 60, target_max_seconds=10 * 60,
    words_per_minute=155,
    scene_min_seconds=3.0, scene_max_seconds=8.0,
    hook_max_seconds=30.0,
    rehook_every_seconds=75,
)

# Shorts: menos de 1 minuto, apurando al máximo (objetivo 52–59 s).
# Nota: YouTube Shorts admite hasta 3 min, pero el objetivo PILO es <60 s para que
# la misma pieza sirva en Shorts, TikTok e Instagram Reels sin recortes.
SHORT = FormatSpec(
    name="SHORT", aspect="9:16", width=1080, height=1920,
    min_seconds=50, max_seconds=59,
    target_min_seconds=52, target_max_seconds=59,
    words_per_minute=175,
    scene_min_seconds=1.5, scene_max_seconds=3.5,
    hook_max_seconds=1.5,
    rehook_every_seconds=12,
)

FORMATS = {"LONG": LONG, "SHORT": SHORT}


def get_format(name: str) -> FormatSpec:
    try:
        return FORMATS[name.upper()]
    except KeyError:
        raise ValueError(f"Formato desconocido: {name!r}. Usa LONG o SHORT.") from None


def decide_format(
    sub_points: int,
    has_story_arc: bool,
    single_surprising_fact: bool,
    needs_explanation_steps: int,
) -> tuple[str, str]:
    """Heurística determinista de apoyo al Agente Guionista.

    - sub_points: cuántas ideas/capítulos distintos necesita la idea para entenderse.
    - has_story_arc: hay una historia con inicio, conflicto y desenlace (biografías,
      ascenso/caída de empresas, crisis).
    - single_surprising_fact: la idea se sostiene sobre UN dato/giro sorprendente.
    - needs_explanation_steps: pasos de explicación técnica necesarios.

    Devuelve (formato, razón).
    """
    long_score = 0
    short_score = 0
    if sub_points >= 4:
        long_score += 2
    elif sub_points <= 2:
        short_score += 2
    if has_story_arc:
        long_score += 2
    if single_surprising_fact:
        short_score += 3
    if needs_explanation_steps >= 3:
        long_score += 2
    elif needs_explanation_steps <= 1:
        short_score += 1

    if short_score > long_score:
        return "SHORT", (
            f"Idea compacta (short={short_score} vs long={long_score}): se resuelve con "
            "un hook + un giro + un payoff en <60 s."
        )
    return "LONG", (
        f"Idea con profundidad (long={long_score} vs short={short_score}): necesita "
        "capítulos, escalada y payoffs para sostener 8–10 min de watch time."
    )
