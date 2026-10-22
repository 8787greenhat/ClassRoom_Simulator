import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from classroom_simulator.evaluation import (
    EvaluationScenario,
    SCENARIOS,
    evaluate_provider,
    score_response,
)
from classroom_simulator.llm import MockProvider


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
        self.assertEqual(report["evaluator_version"], "1.0")
        self.assertEqual(report["prompt_version"], "density-v3")
        self.assertEqual(len(report["scenario_summaries"]), len(SCENARIOS))
        self.assertTrue(all(item["pass_rate"] == 1.0 for item in report["scenario_summaries"]))

    def test_evaluation_rejects_non_positive_repeat_count(self):
        with self.assertRaises(ValueError):
            evaluate_provider(MockProvider(), repeats=0)

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
