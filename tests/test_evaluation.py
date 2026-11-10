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


class FailingProvider(LLMProvider):
    name = "failing-test"

    def reply(self, profile, state, teacher_message, topic, objective):
        raise RuntimeError("invalid model JSON")


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
        self.assertEqual(report["prompt_version"], "density-v4.2")
        self.assertEqual(report["suite"], "baseline")
        self.assertTrue(all("behavior_type" in item for item in report["results"]))
        self.assertTrue(all("guarded" in item for item in report["results"]))
        self.assertTrue(all("human_review" in item for item in report["results"]))
        self.assertTrue(all(item["human_review"]["status"] == "pending" for item in report["results"]))
        self.assertEqual(report["human_review_status"]["pending"], report["total_runs"])
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

    def test_response_source_separates_raw_guarded_mock_and_fallback(self):
        self.assertEqual(response_source("ollama", False), "raw_ollama")
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
