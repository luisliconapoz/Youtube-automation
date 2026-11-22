"""CLI de PILO STUDIO.

  python -m pilo_studio channels
  python -m pilo_studio system-prompt --brand FACT_STICK --format SHORT [--out f.md]
  python -m pilo_studio validate plan.json
  python -m pilo_studio new --plan plan.json            # crea proyecto y corre el Tubo
  python -m pilo_studio run <carpeta_proyecto> [--until IMAGE_PROMPTS] [--reset-from IMAGES]
  python -m pilo_studio status <carpeta_proyecto>
  python -m pilo_studio ideas --brand FACT_STICK
  python -m pilo_studio decide-format --sub-points 2 --single-fact
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .agents.scriptwriter import build_system_prompt, build_user_prompt
from .core.brand import active_brands, check_character_exclusivity, load_registry
from .core.brand import load_brand
from .core.formats import decide_format
from .core.paths import OUTPUT_DIR
from .ideas.registry import IdeaRegistry
from .pipeline.orchestrator import Orchestrator, load_config
from .pipeline.project import Project
from .pipeline.state import ORDER, PipelineState, Stage
from .qa.validator import validate_plan


def cmd_channels(a):
    reg = load_registry()
    print(f"Modo de operación: {reg['operating_mode']}")
    for ch in reg["channels"]:
        mark = "● ACTIVO  " if ch["active"] else "○ reservado"
        print(f"  {ch['slot']:>2}. {mark} {ch['id']:<22} {ch['niche']}")
    probs = check_character_exclusivity(active_brands())
    print("Exclusividad de personajes:", "OK" if not probs else "; ".join(probs))
    for b in active_brands():
        for q in b.open_questions:
            print(f"  ? {b.id}: {q}")


def cmd_system_prompt(a):
    text = build_system_prompt(a.brand, a.format)
    user = build_user_prompt(a.brand, a.format, a.topic)
    if a.out:
        Path(a.out).write_text(text + "\n\n---\nUSER:\n" + user + "\n", encoding="utf-8")
        print(f"System prompt escrito en {a.out}")
    else:
        print(text)
        print("\n---\nUSER:\n" + user)


def cmd_validate(a):
    plan = json.loads(Path(a.plan).read_text(encoding="utf-8"))
    r = validate_plan(plan)
    print(r.summary())
    return 0 if r.ok else 1


def _print_status(project: Project):
    st = PipelineState(project.path("state.json"))
    print(f"Proyecto: {project.root}")
    for s in ORDER:
        rec = st.get(s)
        extra = rec.get("note") or rec.get("reason") or ""
        secs = f"{rec['seconds']}s" if "seconds" in rec else ""
        print(f"  {s.value:<14} {rec['status']:<8} {secs:>8}  {extra}")
    costs = project.path("costs.json")
    if costs.exists():
        print(f"  Costo acumulado: ${sum(e['usd'] for e in json.loads(costs.read_text())):.2f}")


def _run(project: Project, until: str | None, test_images: bool = False):
    brand_id = project.brand_dir.name
    status = Orchestrator(project, **_providers(brand_id, test_images)).run(until=Stage(until) if until else None)
    _print_status(project)
    print(f"\nResultado: {status.value}")
    return 0 if status.value in ("done", "blocked") else 1


def _make_llm():
    """Claude si hay ANTHROPIC_API_KEY; si no, None (la etapa PLAN queda BLOCKED con instrucciones)."""
    import os
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    from .providers.llm_claude import ClaudeLLM
    cfg = load_config()["llm_claude"]
    return ClaudeLLM(model=cfg["model"], max_tokens=cfg["max_tokens"],
                     est_usd_per_plan=cfg["est_usd_per_plan"])


def _providers(brand_id: str, test_images: bool) -> dict:
    """Herramientas gratis conectadas: Kokoro (voz) y ffmpeg (montaje). Imágenes de prueba opcionales."""
    out = {}
    try:
        from .providers.tts_kokoro import KokoroTTS
        out["tts"] = KokoroTTS()
    except ImportError:
        print("Aviso: kokoro-onnx no instalado (pip install kokoro-onnx soundfile)")
    from .providers.render_ffmpeg import FFmpegRenderer
    out["renderer"] = FFmpegRenderer()
    if test_images:
        from .providers.image_placeholder import PlaceholderImages
        out["image"] = PlaceholderImages(brand_id)
    elif os.environ.get("PILO_IMAGES", "") == "gemini":
        from .providers.image_gemini import GeminiImages
        out["image"] = GeminiImages()
    return out


def _run_generated(a):
    """pilo new --brand X --format Y [--topic ...]: el Agente Guionista genera el plan."""
    from .agents.scriptwriter import build_user_prompt
    from .core.brand import load_brand
    brand = load_brand(a.brand)
    project = Project.create(brand.id, a.format, a.topic or brand.niche)
    project.write_json("request.json", {"brand": brand.id, "format": a.format, "topic": a.topic})
    status = Orchestrator(project, llm=_make_llm(), **_providers(brand.id, a.test_images)).run(
        until=Stage(a.until) if a.until else None)
    _print_status(project)
    print(f"\nResultado: {status.value}")
    return 0 if status.value in ("done", "blocked") else 1


def batch_order(brand_ids: list[str], count: int) -> list[str]:
    """Ronda a ronda: un video de cada canal activo antes de pasar a la siguiente ronda."""
    return [b for _ in range(count) for b in brand_ids]


def cmd_batch(a):
    from .core.brand import active_brands
    brands = [b.id for b in active_brands()]
    llm = _make_llm()
    rows = []
    for brand_id in batch_order(brands, a.count):
        project = Project.create(brand_id, a.format, load_brand(brand_id).niche)
        project.write_json("request.json", {"brand": brand_id, "format": a.format, "topic": None})
        status = Orchestrator(project, llm=llm, **_providers(brand_id, a.test_images)).run()
        rows.append((brand_id, project.root.name, status.value))
    for brand_id, name, st in rows:
        print(f"{brand_id:<12} {st:<8} {name}")
    return 0 if all(st in ("done", "blocked") for _, _, st in rows) else 1


def cmd_new(a):
    if a.brand:
        return _run_generated(a)
    plan = json.loads(Path(a.plan).read_text(encoding="utf-8"))
    r = validate_plan(plan)
    if not r.ok:
        print(r.summary())
        print("\nNo se crea el proyecto: corrige el plan primero (no se gasta nada).")
        return 1
    project = Project.create(plan["brand"], plan["format"], plan["title"])
    project.write_json("plan.json", plan)
    return _run(project, a.until, a.test_images)


def cmd_run(a):
    project = Project(Path(a.project))
    if a.reset_from:
        PipelineState(project.path("state.json")).reset_from(Stage(a.reset_from))
    return _run(project, a.until, a.test_images)


def cmd_status(a):
    _print_status(Project(Path(a.project)))


def cmd_ideas(a):
    for i in IdeaRegistry(a.brand.upper(), OUTPUT_DIR).all():
        print(f"  [{i.get('format', '?'):5}] {i.get('registered_at', '')[:10]}  {i.get('title')}")


def cmd_decide_format(a):
    fmt, why = decide_format(a.sub_points, a.story_arc, a.single_fact, a.steps)
    print(f"{fmt}: {why}")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="pilo", description="PILO STUDIO — El Tubo")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("channels").set_defaults(fn=cmd_channels)

    p = sub.add_parser("system-prompt")
    p.add_argument("--brand", required=True)
    p.add_argument("--format", required=True, choices=["LONG", "SHORT"])
    p.add_argument("--topic")
    p.add_argument("--out")
    p.set_defaults(fn=cmd_system_prompt)

    p = sub.add_parser("validate")
    p.add_argument("plan")
    p.set_defaults(fn=cmd_validate)

    stages = [s.value for s in Stage]
    p = sub.add_parser("new")
    p.add_argument("--test-images", action="store_true", help="imágenes de PRUEBA gratis (no publicar)")
    p.add_argument("--plan")
    p.add_argument("--brand")
    p.add_argument("--format", choices=["LONG", "SHORT"], default="SHORT")
    p.add_argument("--topic")
    p.add_argument("--until", choices=stages)
    p.set_defaults(fn=cmd_new)

    p = sub.add_parser("batch")
    p.add_argument("--test-images", action="store_true", help="imágenes de PRUEBA gratis (no publicar)")
    p.add_argument("--count", type=int, default=1, help="rondas: un video por canal activo en cada una")
    p.add_argument("--format", choices=["LONG", "SHORT"], default="LONG")
    p.set_defaults(fn=cmd_batch)

    p = sub.add_parser("run")
    p.add_argument("--test-images", action="store_true", help="imágenes de PRUEBA gratis (no publicar)")
    p.add_argument("project")
    p.add_argument("--until", choices=stages)
    p.add_argument("--reset-from", choices=stages)
    p.set_defaults(fn=cmd_run)

    p = sub.add_parser("status")
    p.add_argument("project")
    p.set_defaults(fn=cmd_status)

    p = sub.add_parser("ideas")
    p.add_argument("--brand", required=True)
    p.set_defaults(fn=cmd_ideas)

    p = sub.add_parser("decide-format")
    p.add_argument("--sub-points", type=int, required=True)
    p.add_argument("--story-arc", action="store_true")
    p.add_argument("--single-fact", action="store_true")
    p.add_argument("--steps", type=int, default=1)
    p.set_defaults(fn=cmd_decide_format)

    a = ap.parse_args(argv)
    return a.fn(a) or 0


if __name__ == "__main__":
    sys.exit(main())
