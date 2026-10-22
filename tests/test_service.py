import tempfile
import unittest
from pathlib import Path

from classroom_simulator.db import Database
from classroom_simulator.llm import MockProvider, enforce_role_consistency
from classroom_simulator.models import StudentState
from classroom_simulator.roles import PROFILES_BY_ID
from classroom_simulator.service import ClassroomService


class ClassroomServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        database = Database(Path(self.temp_dir.name) / "test.db")
        self.service = ClassroomService(database, MockProvider())

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_session_starts_with_five_independent_students(self):
        snapshot = self.service.create_session()
        self.assertEqual(len(snapshot["students"]), 5)
        self.assertEqual({student["id"] for student in snapshot["students"]}, {
            "active", "typical", "misconception", "reserved", "distracted"
        })
        memories = [student["state"]["memory"] for student in snapshot["students"]]
        self.assertTrue(all(memory == [] for memory in memories))

    def test_teacher_can_target_a_named_student(self):
        snapshot = self.service.create_session()
        snapshot = self.service.send_teacher_message(
            snapshot["session"]["id"], "小哲，物體越重，密度就一定越大嗎？"
        )
        student_event = snapshot["events"][-1]
        self.assertEqual(student_event["speaker_id"], "misconception")
        self.assertIn("為什麼", student_event["content"])

    def test_memory_is_isolated_by_student(self):
        snapshot = self.service.create_session()
        session_id = snapshot["session"]["id"]
        snapshot = self.service.send_teacher_message(session_id, "小哲，你先說說看。")
        students = {student["id"]: student for student in snapshot["students"]}
        self.assertEqual(len(students["misconception"]["state"]["memory"]), 2)
        self.assertEqual(len(students["active"]["state"]["memory"]), 0)

    def test_misconception_does_not_disappear_after_simple_praise(self):
        snapshot = self.service.create_session()
        session_id = snapshot["session"]["id"]
        snapshot = self.service.send_teacher_message(session_id, "小哲，你回答得很好。")
        student = next(item for item in snapshot["students"] if item["id"] == "misconception")
        self.assertEqual(student["state"]["misconception_strength"], 3)

    def test_explanation_and_check_reduce_misconception_one_step(self):
        snapshot = self.service.create_session()
        session_id = snapshot["session"]["id"]
        snapshot = self.service.send_teacher_message(
            session_id,
            "小哲，密度是質量除以體積，所以不能只看質量。你用一個例子再說一次，對不對？",
        )
        student = next(item for item in snapshot["students"] if item["id"] == "misconception")
        self.assertEqual(student["state"]["misconception_strength"], 2)

    def test_role_guard_blocks_premature_llm_agreement(self):
        profile = PROFILES_BY_ID["misconception"]
        state = StudentState(role_id=profile.id, misconception_strength=3)
        response, emotion, guarded = enforce_role_consistency(
            profile,
            state,
            "質量大的物體密度不一定大，還要看體積。",
            "confident",
        )
        self.assertTrue(guarded)
        self.assertIn("還是不懂", response)
        self.assertEqual(emotion, "confused")

    def test_role_guard_blocks_agreement_disguised_as_a_question(self):
        profile = PROFILES_BY_ID["misconception"]
        state = StudentState(role_id=profile.id, misconception_strength=3)
        response, emotion, guarded = enforce_role_consistency(
            profile,
            state,
            "是的，我同意了。但我有點疑惑，重量大的東西，體積一定大嗎？",
            "confused",
        )

        self.assertTrue(guarded)
        self.assertIn("還是不懂", response)
        self.assertEqual(emotion, "confused")

    def test_role_guard_blocks_thanking_teacher_for_the_correction(self):
        profile = PROFILES_BY_ID["misconception"]
        state = StudentState(role_id=profile.id, misconception_strength=3)
        response, _, guarded = enforce_role_consistency(
            profile,
            state,
            "重量和密度沒有直接關係，謝謝你的提醒。",
            "confident",
        )

        self.assertTrue(guarded)
        self.assertIn("還是不懂", response)

    def test_role_guard_makes_distracted_student_request_the_missing_question(self):
        profile = PROFILES_BY_ID["distracted"]
        state = StudentState(role_id=profile.id)
        response, emotion, guarded = enforce_role_consistency(
            profile,
            state,
            "聽清楚了，密度是質量除以體積。",
            "neutral",
            "小宇，你有在聽嗎？請回答剛才的問題。",
        )

        self.assertTrue(guarded)
        self.assertIn("沒跟上", response)
        self.assertEqual(emotion, "confused")

    def test_role_guard_does_not_override_a_concrete_distracted_question(self):
        profile = PROFILES_BY_ID["distracted"]
        state = StudentState(role_id=profile.id)
        response, _, guarded = enforce_role_consistency(
            profile,
            state,
            "我覺得還要看體積。",
            "neutral",
            "小宇，質量一樣時要怎麼比較密度？",
        )

        self.assertFalse(guarded)
        self.assertEqual(response, "我覺得還要看體積。")


if __name__ == "__main__":
    unittest.main()

