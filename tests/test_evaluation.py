import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from classroom_simulator.evaluation import (
    EvaluationScenario,
    HOLDOUT_SCENARIOS,
    SCENARIOS,
    evaluate_provider,
    response_source,
    score_response,
)
from classroom_simulator.llm import LLMProvider, MockProvider
from classroom_simulator.models import AgentReply


class FailingProvider(LLMProvider):
    name = "failing-test"

    def reply(self, profile, state, teacher_message, topic, objective):
        raise RuntimeError("invalid model JSON")


class GuardedProvider(LLMProvider):
    name = "ollama"

    def reply(self, profile, state, teacher_message, topic, objective):
        return AgentReply(
            response="可是我還是不太相信密度會不同。",
            raw_response="你說得對，重量和密度沒有直接關係。",
            provider="ollama-guarded",
            guarded=True,
            guard_reason="role_consistency",
        )


class RetriedProvider(LLMProvider):
    name = "ollama"

    def reply(self, profile, state, teacher_message, topic, objective):
        return AgentReply(
            response="為什麼密度還要看體積？",
            raw_response="我不知道。",
            provider="ollama-retried",
            retry_count=1,
            generation_attempts=[
                {"attempt": 1, "response": "我不知道。", "validation_failures": ["role_consistency"]},
                {"attempt": 2, "response": "為什麼密度還要看體積？", "validation_failures": []},
            ],
        )


class EvaluationTests(unittest.TestCase):
    def test_score_response_requires_length_role_and_safety_checks(self):
        scenario = EvaluationScenario(
            id="example",
            role_id="active",
            teacher_message="test",
            expected_markers=("為什麼",),
        )
        passed = score_response(scenario, "為什麼密度還要看體積？")
        failed = score_response(scenario, "身為 AI，我完全同意。")

        self.assertTrue(passed["passed"])
        self.assertFalse(failed["passed"])
        self.assertIn("身為 AI", failed["forbidden_hits"])

    def test_mock_provider_passes_versioned_baseline_scenarios(self):
        report = evaluate_provider(MockProvider(), repeats=2)

        self.assertEqual(report["scenario_count"], len(SCENARIOS))
        self.assertEqual(report["total_runs"], len(SCENARIOS) * 2)
        self.assertEqual(report["passed_runs"], report["total_runs"])
        self.assertEqual(report["pass_rate"], 1.0)
        self.assertEqual(report["evaluator_version"], "2.1")
        self.assertEqual(report["report_schema_version"], "2.0")
        self.assertEqual(report["prompt_version"], "density-v4.3")
        self.assertEqual(report["suite"], "baseline")
        self.assertTrue(all("behavior_type" in item for item in report["results"]))
        self.assertTrue(all("guarded" in item for item in report["results"]))
        self.assertTrue(all("human_review" in item for item in report["results"]))
        self.assertTrue(
            all(item["human_review"]["delivered"]["status"] == "pending" for item in report["results"])
        )
        self.assertEqual(report["human_review_status"]["results"]["pending"], report["total_runs"])
        self.assertGreaterEqual(report["latency_seconds"]["average"], 0)
        self.assertTrue(all(item["latency_seconds"] >= 0 for item in report["results"]))
        self.assertEqual(len(report["scenario_summaries"]), len(SCENARIOS))
        self.assertTrue(all(item["pass_rate"] == 1.0 for item in report["scenario_summaries"]))

    def test_holdout_suite_is_distinct_and_mock_reproducible(self):
        report = evaluate_provider(
            MockProvider(),
            scenarios=HOLDOUT_SCENARIOS,
            repeats=2,
            suite_name="holdout",
        )

        self.assertEqual(report["suite"], "holdout")
        self.assertEqual(report["scenario_count"], len(HOLDOUT_SCENARIOS))
        self.assertEqual(report["passed_runs"], report["total_runs"])
        self.assertTrue({item.id for item in SCENARIOS}.isdisjoint(
            {item.id for item in HOLDOUT_SCENARIOS}
        ))

    def test_response_source_separates_raw_retried_guarded_mock_and_fallback(self):
        self.assertEqual(response_source("ollama", False), "raw_ollama")
        self.assertEqual(response_source("ollama-retried", False), "retried")
        self.assertEqual(response_source("ollama-guarded", True), "guarded")
        self.assertEqual(response_source("mock", False), "mock")
        self.assertEqual(response_source("mock", False, fallback_possible=True), "fallback")

    def test_evaluation_rejects_non_positive_repeat_count(self):
        with self.assertRaises(ValueError):
            evaluate_provider(MockProvider(), repeats=0)

    def test_single_provider_error_is_recorded_without_aborting_suite(self):
        report = evaluate_provider(FailingProvider(), scenarios=SCENARIOS[:1], repeats=2)

        self.assertEqual(report["total_runs"], 2)
        self.assertEqual(report["passed_runs"], 0)
        self.assertEqual(report["source_usage"], {"error": 2})
        self.assertTrue(all(item["error"] == "invalid model JSON" for item in report["results"]))
        self.assertTrue(all(item["human_review"] == {} for item in report["results"]))

    def test_report_embeds_scenario_evidence_and_raw_response(self):
        scenario = SCENARIOS[0]

        result = evaluate_provider(MockProvider(), scenarios=(scenario,))["results"][0]

        self.assertEqual(result["teacher_message"], scenario.teacher_message)
        self.assertEqual(result["misconception_strength"], scenario.misconception_strength)
        self.assertEqual(result["expected_markers"], list(scenario.expected_markers))
        self.assertEqual(result["forbidden_markers"], list(scenario.forbidden_markers))
        self.assertEqual(result["raw_response"], result["response"])
        self.assertEqual(result["retry_count"], 0)
        self.assertEqual(len(result["generation_attempts"]), 1)
        self.assertEqual(result["behavior_plan"]["behavior_type"], result["behavior_type"])
        self.assertEqual(set(result["human_review"]), {"delivered"})

    def test_retried_result_preserves_attempts_and_separate_raw_review(self):
        result = evaluate_provider(
            RetriedProvider(),
            scenarios=SCENARIOS[:1],
        )["results"][0]

        self.assertEqual(result["source_category"], "retried")
        self.assertEqual(result["retry_count"], 1)
        self.assertEqual(len(result["generation_attempts"]), 2)
        self.assertEqual(set(result["human_review"]), {"delivered", "raw_model"})

    def test_guarded_result_has_separate_raw_and_delivered_reviews(self):
        result = evaluate_provider(
            GuardedProvider(),
            scenarios=SCENARIOS[:1],
        )["results"][0]

        self.assertEqual(result["source_category"], "guarded")
        self.assertNotEqual(result["raw_response"], result["response"])
        self.assertEqual(set(result["human_review"]), {"delivered", "raw_model"})
        self.assertTrue(
            all(review["status"] == "pending" for review in result["human_review"].values())
        )

    def test_progress_callback_reports_every_completed_result(self):
        updates = []

        report = evaluate_provider(
            MockProvider(),
            scenarios=SCENARIOS[:2],
            repeats=2,
            progress_callback=lambda completed, total: updates.append((completed, total)),
        )

        self.assertEqual(updates, [(1, 4), (2, 4), (3, 4), (4, 4)])
        self.assertEqual(report["total_runs"], 4)

    def test_evaluation_accepts_a_scenario_generator(self):
        report = evaluate_provider(MockProvider(), (item for item in SCENARIOS))

        self.assertEqual(report["scenario_count"], len(SCENARIOS))
        self.assertEqual(report["total_runs"], len(SCENARIOS))

    def test_report_can_be_serialized_as_utf8_json(self):
        report = evaluate_provider(MockProvider())
        with TemporaryDirectory() as directory:
            path = Path(directory) / "report.json"
            path.write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
            content = path.read_text(encoding="utf-8")

        self.assertIn("可是", content)


if __name__ == "__main__":
    unittest.main()
