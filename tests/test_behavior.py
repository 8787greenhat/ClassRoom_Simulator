import unittest

from classroom_simulator.behavior import enforce_behavior_consistency, plan_student_behavior
from classroom_simulator.models import StudentState
from classroom_simulator.roles import PROFILES_BY_ID


class BehaviorPlanningTests(unittest.TestCase):
    def setUp(self):
        self.profile = PROFILES_BY_ID["distracted"]

    def test_generic_recall_prompt_means_student_missed_the_question(self):
        state = StudentState(role_id=self.profile.id)
        behavior = plan_student_behavior(
            self.profile,
            state,
            "小宇，你有在聽嗎？請回答剛才的問題。",
        )
        self.assertEqual(behavior, "distracted")

    def test_first_concrete_named_question_is_on_task(self):
        state = StudentState(role_id=self.profile.id)
        behavior = plan_student_behavior(
            self.profile,
            state,
            "小宇，質量相同時要怎麼比較密度？",
        )
        self.assertEqual(behavior, "on_task")

    def test_concrete_named_question_redirects_after_prior_participation(self):
        state = StudentState(role_id=self.profile.id, participation_count=1)
        behavior = plan_student_behavior(
            self.profile,
            state,
            "小宇，回到問題：質量相同時要怎麼比較密度？",
        )
        self.assertEqual(behavior, "redirected")

    def test_long_lecture_alternates_imaginative_and_off_topic_behavior(self):
        message = "老師連續說明了一大段內容，還用了好幾個生活例子，希望全班先記住定義再一起回答問題，不過沒有點名任何學生。"
        imaginative = plan_student_behavior(
            self.profile,
            StudentState(role_id=self.profile.id, participation_count=0),
            message,
        )
        off_topic = plan_student_behavior(
            self.profile,
            StudentState(role_id=self.profile.id, participation_count=1),
            message,
        )
        self.assertEqual(imaginative, "imaginative")
        self.assertEqual(off_topic, "off_topic")

    def test_other_roles_remain_on_task(self):
        profile = PROFILES_BY_ID["active"]
        behavior = plan_student_behavior(
            profile,
            StudentState(role_id=profile.id),
            "這是一段很長而且沒有具體問題的教師說明。" * 5,
        )
        self.assertEqual(behavior, "on_task")

    def test_imaginative_behavior_replaces_plain_formula_answer(self):
        response, emotion, guarded = enforce_behavior_consistency(
            "imaginative",
            "密度是質量除以體積。",
            "neutral",
        )
        self.assertTrue(guarded)
        self.assertIn("如果", response)
        self.assertEqual(emotion, "curious")

    def test_off_topic_behavior_requires_an_actual_tangent(self):
        response, _, guarded = enforce_behavior_consistency(
            "off_topic",
            "我剛才開小差了，請再說一次。",
            "confused",
        )
        self.assertTrue(guarded)
        self.assertIn("布丁", response)

    def test_matching_behavior_is_not_overridden(self):
        response, _, guarded = enforce_behavior_consistency(
            "imaginative",
            "如果月球縮小成彈珠，密度會變嗎？",
            "curious",
        )
        self.assertFalse(guarded)
        self.assertIn("月球", response)


if __name__ == "__main__":
    unittest.main()
