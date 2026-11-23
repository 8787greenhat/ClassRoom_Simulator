import unittest

from classroom_simulator.behavior import (
    ROLE_RESPONSE_EXAMPLES,
    build_behavior_plan,
    enforce_behavior_consistency,
    plan_student_behavior,
)
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

    def test_structured_plan_explains_intent_without_scripting_response(self):
        plan = build_behavior_plan(
            self.profile,
            StudentState(role_id=self.profile.id),
            "小宇，你有在聽嗎？請回答剛才的問題。",
        )

        self.assertEqual(plan.behavior_type, "distracted")
        self.assertIn("請教師重述", plan.intent)
        self.assertEqual(plan.confidence, "low")
        self.assertIn("沒跟上", plan.required_meanings)
        self.assertNotIn("老師，我剛剛", plan.intent)
        self.assertIsInstance(plan.to_dict()["style"], list)

    def test_every_role_has_exactly_two_curated_examples(self):
        self.assertEqual(set(ROLE_RESPONSE_EXAMPLES), set(PROFILES_BY_ID))
        self.assertTrue(all(len(examples) == 2 for examples in ROLE_RESPONSE_EXAMPLES.values()))

    def test_high_strength_misconception_plan_preserves_current_belief(self):
        profile = PROFILES_BY_ID["misconception"]
        plan = build_behavior_plan(
            profile,
            StudentState(role_id=profile.id, misconception_strength=3),
            "小哲，重量不能決定密度，你同意嗎？",
        )

        self.assertIn("重量直覺", plan.understanding)
        self.assertIn("維持目前理由", plan.intent)
        self.assertEqual(plan.misconception, profile.misconception)

    def test_plan_exposes_concept_state_and_names_weak_concepts(self):
        profile = PROFILES_BY_ID["typical"]
        state = StudentState(
            role_id=profile.id,
            misconception_strength=1,
            concept_mastery={
                "mass": 2,
                "volume": 2,
                "density_ratio": 0,
                "material_invariance": 1,
                "unit_conversion": 0,
            },
            misconception_beliefs={"heavier_means_denser": 1},
        )

        plan = build_behavior_plan(profile, state, "小明，你哪裡不確定？")

        self.assertEqual(plan.concept_mastery["density_ratio"], 0)
        self.assertEqual(plan.misconception_beliefs["heavier_means_denser"], 1)
        self.assertIn("密度是質量與體積的比值", plan.understanding)
        self.assertIn("attention", plan.engagement_state)

    def test_low_willingness_can_produce_visible_silence(self):
        profile = PROFILES_BY_ID["reserved"]
        state = StudentState(
            role_id=profile.id,
            engagement_state={
                "attention": 0.5,
                "willingness_to_answer": 0.05,
                "frustration": 0.4,
                "embarrassment": 0.7,
                "confidence": 0.3,
            },
        )

        plan = build_behavior_plan(profile, state, "質量和體積有什麼關係？")

        self.assertEqual(plan.behavior_type, "silent")

    def test_named_low_confidence_student_answers_hesitantly(self):
        profile = PROFILES_BY_ID["reserved"]
        plan = build_behavior_plan(
            profile,
            StudentState(role_id=profile.id),
            "小安，請說說看密度和體積的關係？",
        )

        self.assertEqual(plan.behavior_type, "hesitant")

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
