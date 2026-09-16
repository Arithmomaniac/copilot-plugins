import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest import mock

import aa_pareto
import build_report


class EffectiveSpecsTests(unittest.TestCase):
    def test_recognizes_reviewed_live_models(self) -> None:
        discovered = [
            {
                "id": "gpt-5.6-sol",
                "supportedReasoningEfforts": ["low", "high"],
            },
            {
                "id": "gpt-5.6-sol-fast",
                "supportedReasoningEfforts": ["low", "medium", "high", "xhigh", "max"],
            },
            {
                "id": "mai-code-1.1-flash",
                "supportedReasoningEfforts": ["low", "medium", "high"],
            },
            {
                "id": "gpt-6-astra",
                "supportedReasoningEfforts": ["low", "medium", "high", "xhigh", "max"],
            },
        ]

        specs, source, omitted_count = build_report.effective_specs(discovered)
        specs_by_id = {spec.copilot_id: spec for spec in specs}

        self.assertEqual(("low", "high"), specs_by_id["gpt-5.6-sol"].efforts)
        self.assertIn("gpt-5.6-sol-fast", specs_by_id)
        self.assertIn("mai-code-1.1-flash", specs_by_id)
        self.assertIn("gpt-6-astra", specs_by_id)
        self.assertEqual(
            {
                "gemini-3.5-flash",
                "gemini-3.6-flash",
                "gemini-3.7-flash",
                "gemini-3.8-flash",
            },
            {
                model_id
                for model_id in specs_by_id
                if model_id.startswith("gemini-")
            },
        )
        self.assertNotIn("gemini-3.1-pro-preview", specs_by_id)
        self.assertNotIn("kimi-k2.7-code", specs_by_id)
        self.assertIn("models.list", source)
        self.assertIn("live-probed", source)
        self.assertEqual(0, omitted_count)


class RuntimeMeasurementTests(unittest.TestCase):
    def test_falls_back_to_rsc_when_api_runtime_is_zero(self) -> None:
        model = {
            "name": "GPT Test (high)",
            "slug": "gpt-test",
            "median_output_tokens_per_second": 0,
            "median_time_to_first_token_seconds": 0,
            "median_time_to_first_answer_token": 0,
        }
        rich = {
            "slug": "gpt-test",
            "medianOutputTokensPerSecond": 84.5,
            "medianTimeToFirstTokenSeconds": 1.6,
            "medianTimeToFirstAnswerTokenSeconds": 1.7,
        }

        self.assertTrue(build_report.valid_runtime(model, rich))
        row = build_report.base_row(model, [], rich)

        self.assertEqual(84.5, row["tok_s"])
        self.assertEqual(1.6, row["ttft"])
        self.assertEqual(
            "AA public RSC",
            row["runtime_sources"]["output_tokens_per_second"],
        )

    def test_prefers_positive_api_runtime_over_rsc(self) -> None:
        model = {
            "median_output_tokens_per_second": 100,
            "median_time_to_first_token_seconds": 2,
        }
        rich = {
            "medianOutputTokensPerSecond": 80,
            "medianTimeToFirstTokenSeconds": 3,
        }

        row = build_report.base_row(model, [], rich)

        self.assertEqual(100.0, row["tok_s"])
        self.assertEqual(2.0, row["ttft"])
        self.assertEqual("AA API", row["runtime_sources"]["output_tokens_per_second"])


class ReportTemplateTests(unittest.TestCase):
    def test_exposes_grok_shape_and_speed_cost_slider(self) -> None:
        self.assertIn("id=\"tradeoff\"", build_report.HTML_TEMPLATE)
        self.assertIn("id=\"xMode\"", build_report.HTML_TEMPLATE)
        self.assertIn("id=\"frontierOnly\"", build_report.HTML_TEMPLATE)
        self.assertIn("kind==='grok'", build_report.HTML_TEMPLATE)
        self.assertIn("function pareto2d", build_report.HTML_TEMPLATE)
        self.assertNotIn("Weighted frontier knee", build_report.HTML_TEMPLATE)
        self.assertNotIn("function spread", build_report.HTML_TEMPLATE)
        self.assertIn("class','frontier-line'", build_report.HTML_TEMPLATE)


class ThreeAxisParetoTests(unittest.TestCase):
    def test_keeps_non_dominated_quality_speed_cost_tradeoffs(self) -> None:
        rows = [
            {"id": "balanced", "quality": 90, "speed": 90, "cost": 5},
            {"id": "quality", "quality": 100, "speed": 70, "cost": 8},
            {"id": "cheap", "quality": 80, "speed": 60, "cost": 1},
            {"id": "dominated", "quality": 80, "speed": 50, "cost": 7},
        ]

        front = aa_pareto.pareto_front(
            rows,
            "quality",
            "speed",
            True,
            "cost",
        )

        self.assertEqual(
            {"balanced", "quality", "cheap"},
            {row["id"] for row in front},
        )

    def test_detects_single_three_axis_dominator(self) -> None:
        rows = [
            {"id": "winner", "quality": 100, "speed": 100, "cost": 1},
            {"id": "other", "quality": 90, "speed": 90, "cost": 2},
        ]

        front = aa_pareto.pareto_front(
            rows,
            "quality",
            "speed",
            True,
            "cost",
        )

        self.assertEqual(["winner"], [row["id"] for row in front])

    def test_price_weight_can_change_efficiency_knee(self) -> None:
        rows = [
            {
                "id": "fast",
                "quality": 100,
                "speed": 100,
                "cost": 4,
                "intelligence": 0,
            },
            {
                "id": "cheap",
                "quality": 90,
                "speed": 50,
                "cost": 1,
                "intelligence": 0,
            },
        ]
        front = aa_pareto.pareto_front(
            rows,
            "quality",
            "speed",
            True,
            "cost",
        )

        speed_first = aa_pareto.picks(
            rows,
            front,
            "quality",
            0,
            "speed",
            True,
            "cost",
            speed_weight=2,
            cost_weight=1,
        )
        price_first = aa_pareto.picks(
            rows,
            front,
            "quality",
            0,
            "speed",
            True,
            "cost",
            speed_weight=1,
            cost_weight=2,
        )

        self.assertEqual("fast", speed_first["quality_at_efficiency"]["id"])
        self.assertEqual("cheap", price_first["quality_at_efficiency"]["id"])

    def test_strict_dominance_requires_improvement_on_every_axis(self) -> None:
        baseline = {"quality": 90, "speed": 50, "cost": 5}

        self.assertTrue(
            aa_pareto.strictly_dominates(
                {"quality": 91, "speed": 51, "cost": 4},
                baseline,
                "quality",
                "speed",
                True,
                "cost",
            )
        )
        self.assertFalse(
            aa_pareto.strictly_dominates(
                {"quality": 91, "speed": 50, "cost": 4},
                baseline,
                "quality",
                "speed",
                True,
                "cost",
            )
        )

    def test_resolves_explicit_model_effort_baseline(self) -> None:
        rows = [
            {"copilot_id": "model", "effort": "low"},
            {"copilot_id": "model", "effort": "high"},
        ]

        self.assertEqual(
            "high",
            aa_pareto.resolve_baseline(rows, "model@high")["effort"],
        )
        with self.assertRaises(ValueError):
            aa_pareto.resolve_baseline(rows, "model")


class CopilotCostScalingTests(unittest.TestCase):
    def test_parses_picker_only_model_from_official_pricing_table(self) -> None:
        page = """
        <table><tbody><tr>
        <td>Gemini 3.8 Flash<sup>1</sup></td><td>GA</td><td>Versatile</td>
        <td>Default</td><td>Not applicable</td><td>$0.75</td>
        <td>$0.075</td><td>$3.75</td>
        </tr></tbody></table>
        """
        with mock.patch.object(build_report, "request_text", return_value=page):
            prices = build_report.fetch_official_copilot_ai_credit_prices()

        self.assertEqual((75.0, 375.0), prices["gemini-3.8-flash"])

    def test_scales_scraped_task_cost_to_copilot_rates(self) -> None:
        row = {
            "metrics": {
                "price.price_1m_input_tokens": 2.0,
                "price.price_1m_output_tokens": 10.0,
                "price.price_1m_blended_3_to_1": 4.0,
                "task.cost_input": 1.0,
                "task.cost_output": 5.0,
                "briefcase.cost_total": 100.0,
            }
        }

        build_report.enrich_copilot_cost(row, (1.0, 5.0))

        self.assertEqual(
            2.0,
            row["metrics"]["price.copilot_ai_credits_blended_3_to_1"],
        )
        self.assertEqual(3.0, row["metrics"]["copilot.ai_credits_per_task"])
        self.assertEqual(
            50.0,
            row["metrics"]["copilot.briefcase_ai_credits_total"],
        )

    def test_scales_briefcase_without_intelligence_cost_components(self) -> None:
        row = {
            "metrics": {
                "price.price_1m_input_tokens": 2.0,
                "price.price_1m_output_tokens": 10.0,
                "price.price_1m_blended_3_to_1": 4.0,
                "briefcase.cost_total": 100.0,
            }
        }

        build_report.enrich_copilot_cost(row, (1.0, 5.0))

        self.assertEqual(
            50.0,
            row["metrics"]["copilot.briefcase_ai_credits_total"],
        )
        self.assertNotIn("copilot.ai_credits_per_task", row["metrics"])

    def test_models_list_ai_credit_prices_override_official_fallback(self) -> None:
        prices, sources = build_report.copilot_ai_credit_prices(
            [
                {
                    "id": "gpt-6-astra",
                    "billing": {
                        "tokenPrices": {
                            "inputPrice": 1000,
                            "outputPrice": 5000,
                        }
                    },
                }
            ],
            {
                "gpt-6-astra": (999, 999),
                "gemini-3.8-flash": (75, 375),
            },
        )

        self.assertEqual((1000, 5000), prices["gpt-6-astra"])
        self.assertEqual((75, 375), prices["gemini-3.8-flash"])
        self.assertIn("models.list", sources["gpt-6-astra"])
        self.assertIn("official", sources["gemini-3.8-flash"])


class TriReviewRowsTests(unittest.TestCase):
    @staticmethod
    def row(model_id: str, coding: float, elapsed: float) -> dict:
        return {
            "copilot_id": model_id,
            "coding": coding,
            "intelligence": coding,
            "ttft": 1.0,
            "task_time": elapsed - 1.0,
        }

    def test_selects_four_families_with_same_family_alternates(self) -> None:
        rows = [
            self.row("claude-opus-5", 76.0, 200.0),
            self.row("claude-opus-5", 74.0, 100.0),
            self.row("gpt-5.6-sol", 78.0, 150.0),
            self.row("gpt-5.6-terra", 70.0, 100.0),
            self.row("gemini-3.7-flash", 76.0, 130.0),
            self.row("gemini-3.6-flash", 72.0, 100.0),
            self.row("grok-4.6", 74.0, 250.0),
            self.row("grok-4.5", 72.0, 200.0),
        ]

        recommendations = aa_pareto.tri_review_rows(
            rows,
            budget_seconds=300.0,
        )

        self.assertEqual(
            [
                "Claude / Anthropic",
                "GPT / OpenAI",
                "Gemini / Google",
                "Grok / xAI",
            ],
            [family for family, _, _, _ in recommendations],
        )
        self.assertEqual(
            [
                "claude-opus-5",
                "gpt-5.6-terra",
                "gemini-3.6-flash",
                "grok-4.5",
            ],
            [alternate["copilot_id"] for _, _, alternate, _ in recommendations],
        )

    def test_keeps_normal_and_alternate_within_budget(self) -> None:
        rows = [
            self.row("grok-4.6", 76.0, 600.0),
            self.row("grok-4.6", 66.0, 180.0),
        ]

        recommendations = aa_pareto.tri_review_rows(rows, budget_seconds=300.0)

        _, normal, alternate, maximum = recommendations[0]
        self.assertLessEqual(aa_pareto.tri_review_elapsed(normal), 300.0)
        self.assertLessEqual(aa_pareto.tri_review_elapsed(alternate), 300.0)
        self.assertEqual(normal, alternate)
        self.assertGreater(aa_pareto.tri_review_elapsed(maximum), 300.0)

    def test_omits_family_without_a_budget_eligible_model(self) -> None:
        rows = [self.row("grok-4.6", 76.0, 600.0)]

        recommendations = aa_pareto.tri_review_rows(rows, budget_seconds=300.0)

        self.assertEqual([], recommendations)


class AxisResolutionTests(unittest.TestCase):
    def test_metric_override_uses_compatible_default_axes(self) -> None:
        self.assertEqual(
            ("intelligence", "task-time", "task-ai-credits", 0.70),
            aa_pareto.resolve_axes("coding", "intelligence", None, None),
        )
        self.assertEqual(
            ("briefcase", "briefcase-turns", "briefcase-ai-credits", 0.70),
            aa_pareto.resolve_axes("coding", "briefcase", None, None),
        )

    def test_explicit_axis_overrides_win(self) -> None:
        self.assertEqual(
            ("intelligence", "task-time", "task-cost", 0.70),
            aa_pareto.resolve_axes(
                "coding",
                "intelligence",
                "task-time",
                "task-cost",
            ),
        )


class CostFallbackTests(unittest.TestCase):
    def test_uses_fallback_with_better_candidate_coverage(self) -> None:
        rows = [
            {"copilot_ai_credits": 0, "token_price": 2.0},
            {"copilot_ai_credits": 0, "token_price": 0},
        ]

        cost_name, reason = aa_pareto.cost_axis_with_fallback(
            rows,
            "ai-credits",
        )

        self.assertEqual("token-price", cost_name)
        self.assertIsNotNone(reason)

    def test_keeps_requested_cost_when_fallback_has_no_more_coverage(self) -> None:
        rows = [
            {"copilot_ai_credits": 1.0, "token_price": 2.0},
            {"copilot_ai_credits": 0, "token_price": 0},
        ]

        cost_name, reason = aa_pareto.cost_axis_with_fallback(
            rows,
            "ai-credits",
        )

        self.assertEqual("ai-credits", cost_name)
        self.assertIsNone(reason)


class CliIntegrationTests(unittest.TestCase):
    @staticmethod
    def run_cli(*arguments: str) -> dict:
        script = Path(__file__).with_name("aa_pareto.py")
        result = subprocess.run(
            [sys.executable, str(script), *arguments, "--json"],
            cwd=script.parent,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise AssertionError(result.stderr or result.stdout)
        return json.loads(result.stdout)

    def test_briefcase_analysis_example(self) -> None:
        output = self.run_cli(
            "--metric",
            "briefcase-analysis",
            "--speed-metric",
            "briefcase-turns",
            "--cost-metric",
            "briefcase-ai-credits",
        )

        self.assertEqual("briefcase-analysis", output["metric"])

    def test_knowledge_work_cost_override_example(self) -> None:
        output = self.run_cli(
            "--task",
            "knowledge-work",
            "--cost-metric",
            "briefcase-cost",
        )

        self.assertEqual("briefcase-cost", output["cost_metric"])

    def test_strict_comparison_example(self) -> None:
        output = self.run_cli(
            "--task",
            "coding",
            "--speed-metric",
            "task-elapsed",
            "--strictly-better-than",
            "gpt-5.4-mini@xhigh",
        )

        self.assertEqual(
            "gpt-5.4-mini (xhigh)",
            output["strictly_better_than"],
        )


if __name__ == "__main__":
    unittest.main()
