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
import sys
from pathlib import Path

from .agents.scriptwriter import build_system_prompt, build_user_prompt
from .core.brand import active_brands, check_character_exclusivity, load_registry
from .core.formats import decide_format
from .core.paths import OUTPUT_DIR
from .ideas.registry import IdeaRegistry
from .pipeline.orchestrator import Orchestrator
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


def _run(project: Project, until: str | None):
    status = Orchestrator(project).run(until=Stage(until) if until else None)
    _print_status(project)
    print(f"\nResultado: {status.value}")
    return 0 if status.value in ("done", "blocked") else 1


def cmd_new(a):
    plan = json.loads(Path(a.plan).read_text(encoding="utf-8"))
    r = validate_plan(plan)
    if not r.ok:
        print(r.summary())
        print("\nNo se crea el proyecto: corrige el plan primero (no se gasta nada).")
        return 1
    project = Project.create(plan["brand"], plan["format"], plan["title"])
    project.write_json("plan.json", plan)
    return _run(project, a.until)


def cmd_run(a):
    project = Project(Path(a.project))
    if a.reset_from:
        PipelineState(project.path("state.json")).reset_from(Stage(a.reset_from))
    return _run(project, a.until)


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
    p.add_argument("--plan", required=True)
    p.add_argument("--until", choices=stages)
    p.set_defaults(fn=cmd_new)

    p = sub.add_parser("run")
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
