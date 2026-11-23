import unittest

from classroom_simulator.learning import (
    apply_teacher_evidence,
    confirm_learning_from_response,
    initial_concept_state,
    stage_teacher_evidence,
)
from classroom_simulator.models import StudentState
from classroom_simulator.roles import PROFILES_BY_ID


class DensityLearningStateTests(unittest.TestCase):
    def test_roles_start_with_distinct_concept_and_belief_states(self):
        active_mastery, active_beliefs = initial_concept_state(PROFILES_BY_ID["active"])
        misconception_mastery, misconception_beliefs = initial_concept_state(
            PROFILES_BY_ID["misconception"]
        )

        self.assertGreater(active_mastery["density_ratio"], misconception_mastery["density_ratio"])
        self.assertEqual(active_beliefs, {})
        self.assertEqual(misconception_beliefs["heavier_means_denser"], 3)

    def test_targeted_ratio_evidence_and_check_update_only_one_level(self):
        profile = PROFILES_BY_ID["misconception"]
        state = StudentState(role_id=profile.id, misconception_strength=3)

        staged = stage_teacher_evidence(
            state,
            profile,
            "密度是質量除以體積，所以不能只看重量。請舉例再說一次，對不對？",
        )
        self.assertEqual(state.misconception_strength, 3)

        update = confirm_learning_from_response(
            state,
            profile,
            staged,
            "密度不能只看重量，還要同時看質量和體積的比值。",
            response_eligible=True,
            confirmation_source="test-model",
        )

        self.assertEqual(update["evidence_concepts"], ["mass", "volume", "density_ratio"])
        self.assertEqual(update["targeted_beliefs"], ["heavier_means_denser"])
        self.assertEqual(update["mastery_changes"]["density_ratio"], {"before": 0, "after": 1})
        self.assertEqual(update["belief_changes"]["heavier_means_denser"], {"before": 3, "after": 2})
        self.assertEqual(state.misconception_strength, 2)
        self.assertEqual(update["status"], "confirmed")

    def test_teacher_evidence_waits_when_student_cannot_explain(self):
        profile = PROFILES_BY_ID["misconception"]
        state = StudentState(role_id=profile.id, misconception_strength=3)
        staged = stage_teacher_evidence(
            state,
            profile,
            "密度是質量除以體積，所以不能只看重量。請用自己的話說說看。",
        )

        update = confirm_learning_from_response(
            state,
            profile,
            staged,
            "我不知道，我還是覺得重的比較密。",
            response_eligible=True,
            confirmation_source="test-model",
        )

        self.assertEqual(update["status"], "not_confirmed")
        self.assertFalse(update["applied"])
        self.assertEqual(state.misconception_strength, 3)

    def test_correct_terms_do_not_confirm_when_student_keeps_weight_belief(self):
        profile = PROFILES_BY_ID["misconception"]
        state = StudentState(role_id=profile.id, misconception_strength=3)
        staged = stage_teacher_evidence(
            state,
            profile,
            "密度是質量除以體積，所以不能只看重量。請用自己的話說說看。",
        )

        update = confirm_learning_from_response(
            state,
            profile,
            staged,
            "我知道還要看質量和體積的比值，可是我還是覺得重的比較密。",
            response_eligible=True,
            confirmation_source="test-model",
        )

        self.assertNotIn(
            "heavier_means_denser",
            update["student_demonstration"]["demonstrated_beliefs"],
        )
        self.assertEqual(state.misconception_strength, 3)

    def test_negated_invariance_does_not_confirm_cutting_belief(self):
        profile = PROFILES_BY_ID["reserved"]
        state = StudentState(role_id=profile.id, misconception_strength=1)
        staged = stage_teacher_evidence(
            state,
            profile,
            "同一種材料切成小塊後密度不變，請用自己的話再說一次。",
        )

        update = confirm_learning_from_response(
            state,
            profile,
            staged,
            "同一種材料切成小塊，我覺得密度會變小、不一樣。",
            response_eligible=True,
            confirmation_source="test-model",
        )

        self.assertEqual(update["student_demonstration"]["demonstrated_beliefs"], [])
        self.assertEqual(state.misconception_strength, 1)

    def test_ineligible_fallback_response_cannot_confirm_learning(self):
        profile = PROFILES_BY_ID["misconception"]
        state = StudentState(role_id=profile.id, misconception_strength=3)
        staged = stage_teacher_evidence(
            state,
            profile,
            "密度是質量除以體積，所以不能只看重量。請用自己的話說說看。",
        )

        update = confirm_learning_from_response(
            state,
            profile,
            staged,
            "密度不能只看重量，還要同時看質量和體積。",
            response_eligible=False,
            confirmation_source="mock-fallback",
        )

        self.assertEqual(update["status"], "ineligible_response_source")
        self.assertEqual(state.misconception_strength, 3)

    def test_evidence_without_understanding_check_does_not_update(self):
        profile = PROFILES_BY_ID["misconception"]
        state = StudentState(role_id=profile.id, misconception_strength=3)

        update = apply_teacher_evidence(
            state,
            profile,
            "密度是質量除以體積，所以不能只看重量。",
        )

        self.assertFalse(update["understanding_check"])
        self.assertFalse(update["applied"])
        self.assertEqual(state.misconception_strength, 3)

    def test_generic_correction_and_praise_do_not_update(self):
        profile = PROFILES_BY_ID["misconception"]
        state = StudentState(role_id=profile.id, misconception_strength=3)

        update = apply_teacher_evidence(state, profile, "你答錯了，不過很努力，再想想。")

        self.assertEqual(update["evidence_concepts"], [])
        self.assertEqual(update["targeted_beliefs"], [])
        self.assertFalse(update["applied"])
        self.assertEqual(state.misconception_strength, 3)

    def test_misaligned_cutting_evidence_does_not_lower_weight_belief(self):
        profile = PROFILES_BY_ID["misconception"]
        state = StudentState(role_id=profile.id, misconception_strength=3)

        staged = stage_teacher_evidence(
            state,
            profile,
            "同一種材料切成小塊後密度不變，請用自己的話再說一次。",
        )
        update = confirm_learning_from_response(
            state,
            profile,
            staged,
            "同一種材料切成小塊，密度還是一樣。",
            response_eligible=True,
            confirmation_source="test-model",
        )

        self.assertEqual(update["targeted_beliefs"], ["smaller_piece_less_dense"])
        self.assertEqual(update["belief_changes"], {})
        self.assertEqual(state.misconception_beliefs["heavier_means_denser"], 3)

    def test_reserved_cutting_belief_updates_with_matching_evidence(self):
        profile = PROFILES_BY_ID["reserved"]
        state = StudentState(role_id=profile.id, misconception_strength=1)

        staged = stage_teacher_evidence(
            state,
            profile,
            "同一種材料切成小塊後密度不變，請用自己的話再說一次。",
        )
        update = confirm_learning_from_response(
            state,
            profile,
            staged,
            "同一種材料切成小塊，密度還是一樣。",
            response_eligible=True,
            confirmation_source="test-model",
        )

        self.assertEqual(update["belief_changes"]["smaller_piece_less_dense"], {"before": 1, "after": 0})
        self.assertEqual(state.misconception_strength, 0)

    def test_unrelated_invariance_statement_is_not_density_evidence(self):
        profile = PROFILES_BY_ID["reserved"]
        state = StudentState(role_id=profile.id, misconception_strength=1)

        update = apply_teacher_evidence(
            state,
            profile,
            "同一種材料切成小塊後顏色不會改變，請用自己的話再說一次。",
        )

        self.assertEqual(update["evidence_concepts"], [])
        self.assertEqual(update["targeted_beliefs"], [])
        self.assertEqual(state.misconception_strength, 1)


if __name__ == "__main__":
    unittest.main()
