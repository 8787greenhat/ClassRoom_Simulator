import tempfile
import unittest
from pathlib import Path

from classroom_simulator.classroom_scenario import FULL_CLASSROOM_TURNS, run_full_classroom
from classroom_simulator.db import Database
from classroom_simulator.llm import MockProvider
from classroom_simulator.service import ClassroomService


class FullClassroomScenarioTests(unittest.TestCase):
    def test_mock_full_classroom_meets_all_hard_checks(self):
        with tempfile.TemporaryDirectory() as directory:
            provider = MockProvider()
            service = ClassroomService(Database(Path(directory) / "test.db"), provider)
            report = run_full_classroom(service, provider)

        summary = report["summary"]
        self.assertEqual(summary["total_turns"], len(FULL_CLASSROOM_TURNS))
        self.assertEqual(summary["passed_turns"], len(FULL_CLASSROOM_TURNS))
        self.assertTrue(summary["passed"])
        self.assertTrue(all(summary["final_checks"].values()))
        self.assertEqual(summary["final_misconception_strength"], 1)
        self.assertEqual(summary["participation"]["distracted"], 2)
        self.assertEqual(summary["provider_usage"], {"mock": 10})

    def test_complete_record_contains_teacher_and_student_events(self):
        with tempfile.TemporaryDirectory() as directory:
            provider = MockProvider()
            service = ClassroomService(Database(Path(directory) / "test.db"), provider)
            report = run_full_classroom(service, provider)

        events = report["final_snapshot"]["events"]
        self.assertEqual(len(events), len(FULL_CLASSROOM_TURNS) * 2)
        self.assertEqual(events[0]["speaker_type"], "teacher")
        self.assertEqual(events[1]["speaker_type"], "student")
        self.assertEqual(report["turns"][4]["behavior_type"], "distracted")
        self.assertEqual(report["turns"][5]["behavior_type"], "redirected")


if __name__ == "__main__":
    unittest.main()
