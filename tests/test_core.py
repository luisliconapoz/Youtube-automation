import copy
import json
import tempfile
import unittest
from pathlib import Path

from pilo_studio.agents.scriptwriter import build_system_prompt
from pilo_studio.core.brand import active_brands, check_character_exclusivity, load_brand
from pilo_studio.core.formats import decide_format
from pilo_studio.core.paths import ROOT
from pilo_studio.ideas.registry import IdeaRegistry
from pilo_studio.pipeline.orchestrator import Orchestrator, load_config
from pilo_studio.pipeline.project import Project
from pilo_studio.pipeline.state import Stage, Status
from pilo_studio.prompts.image_prompt import build_all_prompts
from pilo_studio.providers.base import ImageProvider, ProviderResult
from pilo_studio.qa.validator import validate_plan

EXAMPLE = ROOT / "examples" / "FACT_STICK_SHORT_bank_money.json"


def example_plan():
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


def codes(report):
    return {i.code for i in report.errors}


class TestBrands(unittest.TestCase):
    def test_three_active_brands(self):
        self.assertEqual([b.id for b in active_brands()], ["FACT_STICK", "WILD_MONEY", "MONEY_HOUSE"])

    def test_characters_never_shared_between_brands(self):
        self.assertEqual(check_character_exclusivity(active_brands()), [])

    def test_alias_resolves(self):
        self.assertEqual(load_brand("MONEY_HOUSE").character("coral").id, "BROWN")

    def test_cast_matches_visual_guides(self):
        self.assertEqual(set(load_brand("FACT_STICK").characters), {"BLUE", "GREEN", "PINK", "FARMER", "RICH"})
        self.assertEqual(set(load_brand("WILD_MONEY").characters), {"ORANGE", "PURPLE", "WHITE", "TEAL"})
        self.assertEqual(set(load_brand("MONEY_HOUSE").characters), {"CYAN", "LIME", "BROWN", "GRAY"})

    def test_every_character_has_reference_image(self):
        from pilo_studio.prompts.image_prompt import reference_images_for
        for b in active_brands():
            for cid in b.characters:
                self.assertTrue(reference_images_for(b.id, cid), f"{b.id}/{cid} sin referencia")


class TestValidator(unittest.TestCase):
    def test_example_passes(self):
        r = validate_plan(example_plan())
        self.assertTrue(r.ok, r.summary())

    def test_foreign_character_rejected(self):
        plan = example_plan()
        plan["scenes"][2]["characters"][0]["id"] = "PURPLE"  # es de WILD_MONEY
        self.assertIn("FOREIGN_CHARACTER", codes(validate_plan(plan)))

    def test_repeated_pose_and_expression_rejected(self):
        plan = example_plan()
        plan["scenes"][3]["characters"][0].update(expression="Smug", pose="Explaining")  # igual que escena 3
        c = codes(validate_plan(plan))
        self.assertIn("REPEAT_POSE", c)
        self.assertIn("REPEAT_EXPRESSION", c)

    def test_text_numbers_quotes_3d_rejected(self):
        for field, value, code in [
            ("visual_idea", "a sign with the title of the bank", "TEXT_IN_IMAGE"),
            ("visual_idea", "a coin with 100 on it", "NUMBER_IN_IMAGE"),
            ("visual_idea", 'a bank called "Big"', "QUOTE_IN_IMAGE"),
            ("setting", "a photorealistic bank lobby", "FORBIDDEN_STYLE"),
            ("setting", "bank lobby on a white background", "BACKGROUND"),
        ]:
            plan = example_plan()
            plan["scenes"][5][field] = value
            self.assertIn(code, codes(validate_plan(plan)), value)

    def test_context_word_is_not_text(self):
        plan = example_plan()
        plan["scenes"][5]["visual_idea"] = "coins in context of a building"
        self.assertNotIn("TEXT_IN_IMAGE", codes(validate_plan(plan)))

    def test_short_over_59_seconds_rejected(self):
        plan = example_plan()
        plan["scenes"].append({**copy.deepcopy(plan["scenes"][-2]), "number": 20, "duration_s": 3.5})
        plan["scenes"][-1]["characters"][0].update(expression="Happy", pose="Celebrating")
        plan["scenes"][1]["duration_s"] = 3.5  # 55.5 + 3.5 + 0.5 = 59.5 s
        self.assertIn("DURATION", codes(validate_plan(plan)))

    def test_numbering_gap_rejected(self):
        plan = example_plan()
        plan["scenes"][4]["number"] = 99
        self.assertIn("NUMBERING", codes(validate_plan(plan)))


class TestPrompts(unittest.TestCase):
    def test_numbered_and_clean(self):
        plan = example_plan()
        prompts = build_all_prompts(plan, load_brand("FACT_STICK"))
        self.assertEqual([p.filename for p in prompts][:3], ["001.png", "002.png", "003.png"])
        for p in prompts:
            self.assertNotIn("#", p.prompt, "los hex se dibujan como texto")
            for name in ("BLUE", "RICH", "PINK", "GREEN", "FARMER"):
                self.assertNotRegex(p.prompt, rf"\b{name}\b")
            self.assertIn("black background", p.prompt)
            self.assertIn("text", p.negative_prompt)
            self.assertEqual(p.aspect, "9:16")

    def test_system_prompt_renders_for_all_brands(self):
        for b in ("FACT_STICK", "WILD_MONEY", "MONEY_HOUSE"):
            for f in ("LONG", "SHORT"):
                t = build_system_prompt(b, f, output_dir=Path(tempfile.mkdtemp()))
                self.assertNotIn("{{", t)


class TestIdeas(unittest.TestCase):
    def test_duplicate_detection(self):
        reg = IdeaRegistry("FACT_STICK", Path(tempfile.mkdtemp()))
        reg.add({"title": "Why Banks Lend Money They Don't Have", "angle": "fractional lending"})
        status, _ = reg.check({"title": "Why banks lend money they do not have", "angle": "fractional lending"})
        self.assertEqual(status, "duplicate")
        status, _ = reg.check({"title": "How Inflation Eats Your Salary", "angle": "purchasing power"})
        self.assertEqual(status, "new")

    def test_decide_format(self):
        self.assertEqual(decide_format(1, False, True, 1)[0], "SHORT")
        self.assertEqual(decide_format(5, True, False, 4)[0], "LONG")


class FlakyBlackImages(ImageProvider):
    """Genera PNG negros; falla la primera llamada para probar reintentos."""
    name = "fake"

    def __init__(self):
        self.calls = 0

    def generate(self, prompt, out_path):
        from PIL import Image
        self.calls += 1
        if self.calls == 1:
            raise TimeoutError("GPU ocupada")
        Image.new("RGB", (prompt["width"], prompt["height"]), "black").save(out_path)
        return ProviderResult(out_path, usd=0.01, units=1)


class TestPipeline(unittest.TestCase):
    def setUp(self):
        self.out = Path(tempfile.mkdtemp())
        self.cfg = load_config()
        self.plan = example_plan()
        self.project = Project.create("FACT_STICK", "SHORT", self.plan["title"], self.out)
        self.project.write_json("plan.json", self.plan)

    def test_blocks_without_image_provider_then_resumes(self):
        o = Orchestrator(self.project, self.cfg, sleep=lambda s: None)
        self.assertEqual(o.run(), Status.BLOCKED)
        self.assertEqual(o.state.status(Stage.IMAGE_PROMPTS), Status.DONE)
        self.assertTrue((self.project.dir("prompts") / "019.json").exists())

        img = FlakyBlackImages()
        o2 = Orchestrator(self.project, self.cfg, image=img, sleep=lambda s: None)
        self.assertEqual(o2.run(), Status.BLOCKED)  # ahora se bloquea en VOICE
        self.assertEqual(o2.state.status(Stage.QA_IMAGES), Status.DONE)
        self.assertEqual(o2.state.status(Stage.VOICE), Status.BLOCKED)
        self.assertTrue(self.project.image_path(19).exists())
        self.assertAlmostEqual(o2.costs.total, 0.19)
        # registro anti-repetición
        self.assertEqual(len(IdeaRegistry("FACT_STICK", self.out).all()), 1)

    def test_bad_plan_fails_before_spending(self):
        self.plan["scenes"][0]["characters"][0]["id"] = "PURPLE"
        self.project.write_json("plan.json", self.plan)
        img = FlakyBlackImages()
        o = Orchestrator(self.project, self.cfg, image=img, sleep=lambda s: None)
        self.assertEqual(o.run(), Status.FAILED)
        self.assertEqual(o.state.status(Stage.QA_PLAN), Status.FAILED)
        self.assertEqual(img.calls, 0)

    def test_budget_guard(self):
        cfg = {**self.cfg, "budget_usd_per_video": {"LONG": 3.0, "SHORT": 0.0}}

        class Pricey(FlakyBlackImages):
            def estimate_usd(self, n):
                return 0.05 * n

        o = Orchestrator(self.project, cfg, image=Pricey(), sleep=lambda s: None)
        self.assertEqual(o.run(), Status.FAILED)
        self.assertIn("estimado", o.state.get(Stage.IMAGES)["reason"])

    def test_non_black_image_fails_qa(self):
        from PIL import Image
        o = Orchestrator(self.project, self.cfg, sleep=lambda s: None)
        o.run()
        for n in range(1, 20):
            Image.new("RGB", (1080, 1920), "black" if n != 7 else "white").save(self.project.image_path(n))
        self.assertEqual(o.run(), Status.FAILED)
        self.assertIn("007", self.project.path("qa_images.txt").read_text())



class TestBatch(unittest.TestCase):
    def test_round_robin_one_per_channel(self):
        from pilo_studio.cli import batch_order
        self.assertEqual(batch_order(["A", "B", "C"], 2), ["A", "B", "C", "A", "B", "C"])


class TestPlanGeneration(unittest.TestCase):
    def test_repair_loop_fixes_reported_errors(self):
        from pilo_studio.agents.generate import generate_valid_plan
        good = example_plan()
        bad = copy.deepcopy(good)
        bad["scenes"][2]["characters"][0]["id"] = "PURPLE"   # error de otra marca
        replies = [json.dumps(bad), "```json\n" + json.dumps(good) + "\n```"]
        seen = []

        def complete(system, messages):
            seen.append(messages)
            return replies.pop(0)

        from pilo_studio.providers.llm_claude import extract_json
        plan, attempt = generate_valid_plan(complete, extract_json, "sys", "user")
        self.assertEqual(attempt, 1)
        self.assertIn("FOREIGN_CHARACTER", seen[1][-1]["content"])  # el error llegó al agente
        self.assertTrue(validate_plan(plan).ok)

    def test_gives_up_after_max_repairs(self):
        from pilo_studio.agents.generate import PlanRejected, generate_valid_plan
        from pilo_studio.providers.llm_claude import extract_json
        bad = example_plan()
        bad["scenes"][2]["characters"][0]["id"] = "PURPLE"
        with self.assertRaises(PlanRejected):
            generate_valid_plan(lambda s, m: json.dumps(bad), extract_json, "s", "u", max_repairs=2)

    def test_no_api_key_means_blocked_not_failed(self):
        import os
        from pilo_studio.cli import _make_llm
        old = os.environ.pop("ANTHROPIC_API_KEY", None)
        try:
            self.assertIsNone(_make_llm())
        finally:
            if old: os.environ["ANTHROPIC_API_KEY"] = old


if __name__ == "__main__":
    unittest.main()
