"""El Tubo: Idea → Estructura → Guion → Prompts → Imágenes → Voz → Subtítulos →
Mezcla → Render → QA final → Borrador de publicación (publicación MANUAL).

Cada etapa:
  1. se salta si ya está DONE (reanudable),
  2. comprueba presupuesto antes de gastar,
  3. se reintenta con backoff ante fallos transitorios,
  4. se detiene con BLOCKED (sin error) si falta un proveedor/insumo,
  5. se registra en state.json, costs.json y pipeline.log.
"""
from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Callable

from ..core.brand import load_brand
from ..core.formats import get_format
from ..core.paths import ROOT
from ..ideas.registry import IdeaRegistry
from ..prompts.image_prompt import build_all_prompts, prompts_markdown
from ..qa.validator import validate_plan
from ..providers.base import ImageProvider, LLMProvider, Renderer, TTSProvider
from .project import Project, num
from .state import (BudgetExceeded, CostLedger, ORDER, PipelineState,
                    ProviderNotConfigured, Stage, Status)


class QAFailed(RuntimeError):
    pass


def load_config(path: Path = ROOT / "config" / "pipeline.json") -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _srt_time(t: float) -> str:
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


class Orchestrator:
    def __init__(self, project: Project, config: dict | None = None,
                 llm: LLMProvider | None = None, image: ImageProvider | None = None,
                 tts: TTSProvider | None = None, renderer: Renderer | None = None,
                 sleep: Callable[[float], None] = time.sleep):
        self.p = project
        self.cfg = config or load_config()
        self.llm, self.image, self.tts, self.renderer = llm, image, tts, renderer
        self.state = PipelineState(project.path("state.json"))
        self.costs = CostLedger(project.path("costs.json"))
        self.sleep = sleep
        self.handlers = {
            Stage.PLAN: self.stage_plan,
            Stage.QA_PLAN: self.stage_qa_plan,
            Stage.IMAGE_PROMPTS: self.stage_image_prompts,
            Stage.IMAGES: self.stage_images,
            Stage.QA_IMAGES: self.stage_qa_images,
            Stage.VOICE: self.stage_voice,
            Stage.SUBTITLES: self.stage_subtitles,
            Stage.AUDIO_MIX: self.stage_audio_mix,
            Stage.RENDER: self.stage_render,
            Stage.QA_FINAL: self.stage_qa_final,
            Stage.PUBLISH_DRAFT: self.stage_publish_draft,
        }

    # ------------------------------------------------------------------ util
    @property
    def plan(self) -> dict:
        return self.p.read_json("plan.json")

    def budget_left(self) -> float:
        fmt = self.plan.get("format", "LONG") if self.p.path("plan.json").exists() else "LONG"
        return self.cfg["budget_usd_per_video"][fmt] - self.costs.total

    def charge_guard(self, estimated_usd: float, what: str):
        if estimated_usd > self.budget_left() + 1e-9:
            raise BudgetExceeded(f"{what}: estimado ${estimated_usd:.2f} > restante ${self.budget_left():.2f}")

    # ------------------------------------------------------------------ run
    def run(self, until: Stage | None = None) -> Status:
        """Ejecuta etapas pendientes en orden. Devuelve el estado final."""
        retries = self.cfg["retries"]
        for stage in ORDER:
            if self.state.status(stage) == Status.DONE:
                continue
            while True:
                attempt = self.state.bump_attempt(stage)
                t0 = time.monotonic()
                try:
                    note = self.handlers[stage]() or ""
                except ProviderNotConfigured as e:
                    self.state.mark(stage, Status.BLOCKED, reason=str(e))
                    self.p.log(f"{stage.value} BLOCKED: {e}")
                    return Status.BLOCKED
                except (QAFailed, BudgetExceeded) as e:
                    # No se reintenta: reintentar no cambia el resultado y gasta dinero.
                    self.state.mark(stage, Status.FAILED, reason=str(e))
                    self.p.log(f"{stage.value} FAILED: {e}")
                    return Status.FAILED
                except Exception as e:  # fallo transitorio (red, GPU, timeout)
                    self.p.log(f"{stage.value} intento {attempt} error: {e!r}")
                    if attempt >= retries["max_attempts"]:
                        self.state.mark(stage, Status.FAILED, reason=repr(e))
                        return Status.FAILED
                    backoff = retries["backoff_seconds"]
                    self.sleep(backoff[min(attempt - 1, len(backoff) - 1)])
                    continue
                secs = round(time.monotonic() - t0, 2)
                self.state.mark(stage, Status.DONE, seconds=secs, note=note)
                self.p.log(f"{stage.value} DONE en {secs}s {note}")
                break
            if until and stage == until:
                return Status.DONE
        return Status.DONE

    # ------------------------------------------------------------------ etapas
    def stage_plan(self):
        if not self.p.path("plan.json").exists():
            if not self.llm:
                raise ProviderNotConfigured(
                    "No hay plan.json ni proveedor LLM. Genera el plan con el prompt del "
                    "Agente Guionista (`pilo system-prompt`) y cárgalo con `pilo new --plan archivo.json`."
                )
            from ..agents.generate import PlanRejected, generate_valid_plan
            from ..agents.scriptwriter import build_system_prompt, build_user_prompt
            meta = self.p.read_json("request.json")
            rounds = {"n": 0}

            def _count(attempt, report):
                rounds["n"] = attempt + 1
                self.costs.add("PLAN", self.llm.name, self.llm.estimate_usd(), note=f"ronda {attempt + 1}")

            try:
                plan, _ = generate_valid_plan(
                    self.llm.complete, self.llm.parse,
                    build_system_prompt(meta["brand"], meta["format"]),
                    build_user_prompt(meta["brand"], meta["format"], meta.get("topic")),
                    max_repairs=self.cfg.get("plan_max_repairs", 2), on_attempt=_count)
            except PlanRejected as e:
                self.p.write_text("qa_plan.txt", e.report.summary() + "\n")
                raise QAFailed(str(e)) from None
            self.p.write_json("plan.json", plan)
            if rounds["n"] > 1:
                self.p.log(f"PLAN corregido en {rounds['n']} rondas")
        plan = self.plan
        # Separación de artefactos del Tubo (pasos 1, 2 y 3)
        self.p.write_json("00_idea.json", {
            "brand": plan["brand"], "format": plan["format"], "topic": plan["topic"],
            "title": plan["title"], "title_alternatives": plan.get("title_alternatives", []),
            "format_rationale": plan["format_rationale"], **plan["idea"],
        })
        self.p.write_json("01_structure.json", plan["structure"])
        script = [f"# {plan['title']}", ""]
        for sc in plan["scenes"]:
            script.append(f"[{num(sc['number'])}] {sc['narration']}")
        script += ["", "---", "", plan["script"]["full_text"]]
        self.p.write_text("02_script.md", "\n".join(script) + "\n")
        return f"{len(plan['scenes'])} escenas"

    def stage_qa_plan(self):
        plan = self.plan
        report = validate_plan(plan)
        self.p.write_text("qa_plan.txt", report.summary() + "\n")
        if not report.ok:
            raise QAFailed(f"Plan rechazado ({len(report.errors)} errores). Ver qa_plan.txt")
        # Registrar la idea (anti-repetición) solo cuando el plan es válido
        reg = IdeaRegistry(plan["brand"], self.p.brand_dir.parent)
        status, matches = reg.check({"title": plan["title"], "angle": plan["idea"]["angle"], "topic": plan["topic"]})
        if status == "duplicate" and not any(m[1].get("project") == self.p.root.name for m in matches):
            raise QAFailed(f"Idea repetida: ≈ '{matches[0][1]['title']}' ({matches[0][0]:.2f})")
        if status != "duplicate":
            reg.add({"title": plan["title"], "angle": plan["idea"]["angle"], "topic": plan["topic"],
                     "format": plan["format"], "project": self.p.root.name})
        return f"{len(report.warnings)} avisos"

    def stage_image_prompts(self):
        plan = self.plan
        brand = load_brand(plan["brand"])
        prompts = build_all_prompts(plan, brand)
        for ip in prompts:
            self.p.write_json(f"03_prompts/{num(ip.number)}.json", ip.to_dict())
        self.p.write_text("03_prompts/prompts.md", prompts_markdown(plan, prompts))
        return f"{len(prompts)} prompts"

    def stage_images(self):
        plan = self.plan
        missing = self.p.missing_images(len(plan["scenes"]))
        if not missing:
            return "todas presentes"
        if not self.image:
            raise ProviderNotConfigured(
                f"Faltan {len(missing)} imágenes ({', '.join(num(n) for n in missing[:10])}…). "
                f"Modo manual: genera con 03_prompts/prompts.md y guárdalas como 04_images/001.png…"
            )
        self.charge_guard(self.image.estimate_usd(len(missing)), "IMAGES")
        for n in missing:
            prompt = self.p.read_json(f"03_prompts/{num(n)}.json")
            res = self.image.generate(prompt, self.p.image_path(n))
            self.costs.add("IMAGES", self.image.name, res.usd, 1, num(n))
        return f"{len(missing)} generadas"

    def stage_qa_images(self):
        from ..qa.image_checks import check_image
        plan = self.plan
        fmt = get_format(plan["format"])
        problems = []
        for n in range(1, len(plan["scenes"]) + 1):
            problems += [f"{num(n)}: {p}" for p in check_image(self.p.image_path(n), fmt)]
        self.p.write_text("qa_images.txt", "\n".join(problems) or "OK")
        if problems:
            raise QAFailed(f"{len(problems)} problemas en imágenes. Ver qa_images.txt "
                           "(borra las malas y vuelve a correr: solo se regeneran esas).")
        return "OK"

    def stage_voice(self):
        if not self.tts:
            raise ProviderNotConfigured("Proveedor de voz no conectado (Kokoro/VoiceStudio/ElevenLabs). Fase 3 del plan.")
        plan = self.plan
        brand = load_brand(plan["brand"])
        todo = [s for s in plan["scenes"] if not self.p.voice_path(s["number"]).exists()]
        self.charge_guard(self.tts.estimate_usd(sum(len(s["narration"]) for s in todo)), "VOICE")
        for s in todo:
            res = self.tts.synthesize(s["narration"], brand.voice, self.p.voice_path(s["number"]))
            self.costs.add("VOICE", self.tts.name, res.usd, len(s["narration"]), num(s["number"]))
        return f"{len(todo)} clips"

    def stage_subtitles(self):
        """SRT + timeline.json (insumo de Remotion). Usa la duración real del audio si existe."""
        from ..qa.image_checks import wav_duration
        plan = self.plan
        t, srt, timeline = 0.0, [], []
        for s in plan["scenes"]:
            real = wav_duration(self.p.voice_path(s["number"]))
            dur = max(real + 0.15, 0.8) if real else float(s["duration_s"])  # 0.15s de respiro
            srt += [str(s["number"]), f"{_srt_time(t)} --> {_srt_time(t + dur)}", s["narration"], ""]
            timeline.append({
                "number": s["number"], "start": round(t, 3), "duration": round(dur, 3),
                "image": f"04_images/{num(s['number'])}.png",
                "voice": f"05_audio/voice_{num(s['number'])}.wav",
                "narration": s["narration"], "emphasis_words": s.get("emphasis_words", []),
                "on_screen_text": s.get("on_screen_text", ""), "motion": s.get("motion", "slow_zoom_in"),
                "transition_in": s.get("transition_in", "cut"), "sfx": s.get("sfx", "none"),
            })
            t += dur
        self.p.write_text("06_subtitles/subs.srt", "\n".join(srt))
        fmt = get_format(plan["format"])
        self.p.write_json("timeline.json", {"format": fmt.name, "width": fmt.width, "height": fmt.height,
                                            "fps": 30, "total_seconds": round(t, 3), "scenes": timeline,
                                            "audio": plan["audio"]})
        return f"{t:.1f}s"

    def stage_audio_mix(self):
        raise ProviderNotConfigured("Mezcla de audio (voz + música sin copyright + SFX) — Fase 3 del plan.")

    def stage_render(self):
        if not self.renderer:
            raise ProviderNotConfigured("Renderer no conectado (Remotion/Adobe) — Fase 4 del plan.")
        out = self.p.dir("render") / "final.mp4"
        res = self.renderer.render(self.p.root, self.p.read_json("timeline.json"), out)
        self.costs.add("RENDER", self.renderer.name, res.usd)
        return str(out.name)

    def stage_qa_final(self):
        from ..qa.image_checks import probe_video
        plan = self.plan
        fmt = get_format(plan["format"])
        info = probe_video(self.p.dir("render") / "final.mp4")
        problems = []
        if not info:
            problems.append("final.mp4 no existe o no se puede leer")
        else:
            if not (fmt.min_seconds <= info["duration"] <= fmt.max_seconds):
                problems.append(f"duración {info['duration']:.1f}s fuera de {fmt.min_seconds}-{fmt.max_seconds}s")
            if (info["width"], info["height"]) != (fmt.width, fmt.height):
                problems.append(f"resolución {info['width']}x{info['height']} ≠ {fmt.width}x{fmt.height}")
            if not info["has_audio"]:
                problems.append("sin pista de audio")
        if problems:
            raise QAFailed("; ".join(problems))
        return f"{info['duration']:.1f}s"

    def stage_publish_draft(self):
        plan = self.plan
        pd = plan.get("publish_draft", {})
        lines = [
            f"# BORRADOR DE PUBLICACIÓN — revisar y publicar A MANO",
            f"Marca: {plan['brand']} · Formato: {plan['format']}",
            "", "## Título", plan["title"],
            "", "## Alternativas", *[f"- {t}" for t in plan.get("title_alternatives", [])],
            "", "## Descripción (puntos)", *[f"- {d}" for d in pd.get("description_points", [])],
            "", "## Capítulos", *pd.get("chapters", []),
            "", "## Tags", ", ".join(pd.get("tags", [])),
            "", "## Comentario fijado", pd.get("pinned_comment", ""),
            "", "## Checklist humano antes de publicar",
            "- [ ] Vi el video completo y el contenido es correcto (datos verificados)",
            "- [ ] Personalicé título/miniatura/descripción (aporte humano, no copia literal)",
            "- [ ] Activé 'contenido alterado o sintético' si aplica",
            "- [ ] Música y SFX con licencia registrada en 05_audio/LICENSES.txt",
        ]
        self.p.write_text("08_publish/metadata_draft.md", "\n".join(lines) + "\n")
        final = self.p.dir("render") / "final.mp4"
        if final.exists():
            shutil.copy2(final, self.p.ready_dir / f"{self.p.root.name}.mp4")
        return "listo para publicación manual"
