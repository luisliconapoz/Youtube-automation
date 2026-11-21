"""Control de calidad del plan de video (QA Gate 1: antes de gastar en imágenes/voz).

Regla de oro de costos: NINGÚN plan pasa a generación de imágenes o voz si tiene
errores. Los warnings no bloquean, pero quedan registrados en el reporte.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..core import style
from ..core.brand import Brand, load_brand
from ..core.formats import get_format

_DIGIT_RE = re.compile(r"\d")
_QUOTE_RE = re.compile(r"[\"“”«»]")
_WORD_RE = re.compile(r"[\w'’]+", re.UNICODE)


@dataclass
class Issue:
    level: str        # "ERROR" | "WARN"
    code: str
    message: str
    scene: int | None = None

    def __str__(self) -> str:
        where = f"[escena {self.scene:03d}] " if self.scene else ""
        return f"{self.level:5} {self.code}: {where}{self.message}"


@dataclass
class Report:
    issues: list[Issue] = field(default_factory=list)

    def error(self, code, msg, scene=None):
        self.issues.append(Issue("ERROR", code, msg, scene))

    def warn(self, code, msg, scene=None):
        self.issues.append(Issue("WARN", code, msg, scene))

    @property
    def errors(self):
        return [i for i in self.issues if i.level == "ERROR"]

    @property
    def warnings(self):
        return [i for i in self.issues if i.level == "WARN"]

    @property
    def ok(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        head = "APROBADO" if self.ok else "RECHAZADO"
        lines = [f"QA: {head} — {len(self.errors)} errores, {len(self.warnings)} avisos"]
        lines += [str(i) for i in self.issues]
        return "\n".join(lines)


def word_count(text: str) -> int:
    return len(_WORD_RE.findall(text or ""))


def _contains_marker(text: str, markers) -> str | None:
    low = f" {text.lower()} "
    for m in markers:
        # coincidencia por palabra para evitar falsos positivos ("context" ≠ "text")
        if re.search(rf"(?<![\w]){re.escape(m)}(?![\w])", low):
            return m
    return None


def validate_plan(plan: dict, brand: Brand | None = None) -> Report:
    r = Report()

    # ---------- Marca y formato ----------
    try:
        brand = brand or load_brand(plan.get("brand", ""))
    except (FileNotFoundError, ValueError) as e:
        r.error("BRAND", str(e))
        return r
    if not brand.active:
        r.error("BRAND_INACTIVE", f"{brand.id} no está activa en channels.json")
    try:
        fmt = get_format(plan.get("format", ""))
    except ValueError as e:
        r.error("FORMAT", str(e))
        return r

    for key in ("topic", "title", "format_rationale", "idea", "structure", "script", "scenes", "audio"):
        if not plan.get(key):
            r.error("MISSING", f"Falta el campo obligatorio '{key}'")
    if r.errors:
        return r

    title = plan["title"]
    if len(title) > 70:
        r.warn("TITLE_LONG", f"Título de {len(title)} caracteres (>70 se corta en móvil)")

    # ---------- Estructura ----------
    sections = plan["structure"]
    section_ids = {s["section_id"] for s in sections}
    if sections[0].get("type") != "hook":
        r.error("HOOK_FIRST", "La primera sección de la estructura debe ser el hook")
    elif sections[0]["end_s"] > fmt.hook_max_seconds + (0.5 if fmt.name == "SHORT" else 0):
        r.warn("HOOK_SLOW", f"El hook termina en {sections[0]['end_s']}s (máx. recomendado {fmt.hook_max_seconds}s)")
    if fmt.name == "LONG":
        types = [s["type"] for s in sections]
        if types.count("chapter") < 3:
            r.error("CHAPTERS", "Un video largo necesita al menos 3 capítulos")
        if "payoff" not in types:
            r.error("PAYOFF", "Falta la sección 'payoff' (cumplir la promesa del hook)")
        # re-hooks: ninguna sección (excepto chapters con rehook interno) debe superar el intervalo x2
        for s in sections:
            if s["end_s"] - s["start_s"] > fmt.rehook_every_seconds * 2.5:
                r.warn("NO_REHOOK", f"Sección {s['section_id']} dura {s['end_s'] - s['start_s']:.0f}s sin re-hook (máx. ~{fmt.rehook_every_seconds * 2.5:.0f}s)")
    else:
        if sections[-1].get("type") not in ("loop", "payoff"):
            r.warn("SHORT_LOOP", "El Short debería cerrar con 'loop' (la última frase conecta con la primera)")
        if any(s["type"] == "cta" and s["start_s"] < 40 for s in sections):
            r.warn("SHORT_CTA_EARLY", "En Shorts el CTA no va antes del segundo 40 (mata retención)")

    # ---------- Escenas ----------
    scenes = plan["scenes"]
    total = 0.0
    prev_chars: dict[str, tuple[str, str]] = {}
    narrator_scenes = 0
    total_words = 0

    for idx, sc in enumerate(scenes, start=1):
        n = sc.get("number")
        if n != idx:
            r.error("NUMBERING", f"Escena en posición {idx} tiene number={n} (deben ser 1,2,3… sin huecos)", idx)
        n = idx
        dur = float(sc.get("duration_s", 0))
        total += dur
        if dur < fmt.scene_min_seconds:
            r.warn("SCENE_SHORT", f"{dur}s < mínimo {fmt.scene_min_seconds}s (el ojo no alcanza a leer la imagen)", n)
        if dur > fmt.scene_max_seconds:
            r.error("SCENE_LONG", f"{dur}s > máximo {fmt.scene_max_seconds}s sin cambio visual (caída de retención)", n)
        if sc.get("section_id") not in section_ids:
            r.error("SECTION", f"section_id {sc.get('section_id')!r} no existe en la estructura", n)

        # Narración vs. duración
        words = word_count(sc.get("narration", ""))
        total_words += words
        max_words = dur * fmt.words_per_minute / 60 * 1.25
        if words > max_words + 1:
            r.error("NARRATION_OVERFLOW", f"{words} palabras no caben en {dur}s a {fmt.words_per_minute} ppm", n)

        # Personajes, poses, expresiones
        chars = sc.get("characters", [])
        if len(chars) > style.MAX_CHARACTERS_PER_SCENE:
            r.error("TOO_MANY_CHARS", f"{len(chars)} personajes (máx. {style.MAX_CHARACTERS_PER_SCENE})", n)
        current: dict[str, tuple[str, str]] = {}
        for ch in chars:
            cid = str(ch.get("id", "")).upper()
            if not brand.has_character(cid):
                r.error("FOREIGN_CHARACTER", f"{cid} no pertenece a {brand.id} (los personajes jamás se mezclan entre marcas)", n)
                continue
            cid = brand.character(cid).id
            expr, pose = ch.get("expression"), ch.get("pose")
            if expr not in style.EXPRESSIONS:
                r.error("EXPRESSION", f"{cid}: expresión {expr!r} no permitida", n)
            if pose not in style.POSES:
                r.error("POSE", f"{cid}: pose {pose!r} no permitida", n)
            if cid in current:
                r.error("DUP_CHARACTER", f"{cid} aparece dos veces en la misma escena", n)
            current[cid] = (expr, pose)
            if cid in prev_chars:
                p_expr, p_pose = prev_chars[cid]
                if p_pose == pose:
                    r.error("REPEAT_POSE", f"{cid} repite la pose '{pose}' de la escena anterior", n)
                if p_expr == expr:
                    r.error("REPEAT_EXPRESSION", f"{cid} repite la expresión '{expr}' de la escena anterior", n)
        if brand.narrator in current:
            narrator_scenes += 1
        prev_chars = current

        speaker = sc.get("speaker")
        if speaker and not brand.has_character(speaker):
            r.error("FOREIGN_SPEAKER", f"speaker {speaker} no pertenece a {brand.id}", n)

        # Reglas anti-texto / anti-3D / fondo negro en todo lo que llega al generador de imagen
        visual_fields = " ".join([
            sc.get("visual_idea", ""), sc.get("setting", ""),
            " ".join(sc.get("key_objects", [])),
            " ".join(c.get("action", "") for c in chars),
        ])
        m = _contains_marker(visual_fields, style.TEXT_IN_IMAGE_MARKERS)
        if m:
            r.error("TEXT_IN_IMAGE", f"La descripción visual pide texto ('{m}'). Prohibido texto/títulos/números dentro de la imagen; usa on_screen_text", n)
        if _DIGIT_RE.search(visual_fields):
            r.error("NUMBER_IN_IMAGE", "La descripción visual contiene números; prohibido dentro de la imagen (usa on_screen_text)", n)
        if _QUOTE_RE.search(visual_fields):
            r.error("QUOTE_IN_IMAGE", "La descripción visual contiene comillas (suele producir texto en la imagen)", n)
        m = _contains_marker(visual_fields, style.FORBIDDEN_STYLE_MARKERS)
        if m:
            r.error("FORBIDDEN_STYLE", f"Estilo prohibido ('{m}'): solo 2D stickman, nada 3D ni realista", n)
        setting = sc.get("setting", "").lower()
        for bad in ("white background", "colored background", "blue background", "bright background", "fondo blanco"):
            if bad in setting:
                r.error("BACKGROUND", f"'{bad}': el fondo es SIEMPRE negro", n)
        if len(sc.get("key_objects", [])) > 3:
            r.error("CLUTTER", "Más de 3 objetos clave: una sola idea visual principal por escena", n)
        vi = sc.get("visual_idea", "")
        if vi.count(",") + vi.lower().count(" and ") + vi.lower().count(" while ") > 3:
            r.warn("MULTI_IDEA", "visual_idea parece contener varias ideas; debe ser UNA sola idea visual principal", n)

        ost = sc.get("on_screen_text", "")
        if ost and word_count(ost) > 4:
            r.warn("OVERLAY_LONG", f"on_screen_text de {word_count(ost)} palabras (máx. 4 para no distraer)", n)

    # ---------- Duración total ----------
    if total < fmt.min_seconds or total > fmt.max_seconds:
        r.error("DURATION", f"Duración total {total:.1f}s fuera de rango {fmt.min_seconds}-{fmt.max_seconds}s para {fmt.name}")
    elif not (fmt.target_min_seconds <= total <= fmt.target_max_seconds):
        r.warn("DURATION_TARGET", f"Duración {total:.1f}s fuera del objetivo {fmt.target_min_seconds}-{fmt.target_max_seconds}s")
    if fmt.name == "SHORT" and total < 52:
        r.warn("SHORT_UNDERUSED", f"Short de {total:.1f}s: apura el límite (objetivo 52–59s) para más watch time")

    expected = total_words / fmt.words_per_minute * 60
    if total and abs(expected - total) / total > 0.25:
        r.warn("PACE", f"La narración ({total_words} palabras ≈ {expected:.0f}s) no cuadra con la duración visual ({total:.0f}s)")

    # ---------- Reglas de marca ----------
    if scenes:
        ratio = narrator_scenes / len(scenes)
        if ratio < 0.25:
            r.warn("NARRATOR_LOW", f"El narrador {brand.narrator} aparece solo en {ratio:.0%} de las escenas")
        solo_narrator = sum(
            1 for s in scenes
            if [c.get("id", "").upper() for c in s.get("characters", [])] == [brand.narrator]
        ) / len(scenes)
        if solo_narrator > 0.6:
            lvl = r.error if brand.id == "FACT_STICK" else r.warn
            lvl("COLOR_BALANCE", f"{brand.narrator} aparece solo en {solo_narrator:.0%} de las escenas. {brand.color_rule}")
        used = {c.get("id", "").upper() for s in scenes for c in s.get("characters", [])}
        if fmt.name == "LONG" and len(used) < 3:
            r.warn("CAST_SMALL", f"Solo {len(used)} personajes usados; en LONG rota al menos 3 para cambios de patrón")

    if fmt.name == "LONG" and not plan.get("derivatives"):
        r.warn("NO_DERIVATIVES", "Video LONG sin Shorts derivados (Bloque 5): se pierde reutilización")

    return r
