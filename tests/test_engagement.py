import unittest

from classroom_simulator.engagement import (
    ensure_engagement_state,
    initial_engagement_state,
    update_engagement_after_response,
)
from classroom_simulator.models import StudentState
from classroom_simulator.roles import PROFILES_BY_ID


class EngagementStateTests(unittest.TestCase):
    def test_roles_have_distinct_initial_participation_states(self):
        active = initial_engagement_state(PROFILES_BY_ID["active"])
        reserved = initial_engagement_state(PROFILES_BY_ID["reserved"])

        self.assertGreater(active["willingness_to_answer"], reserved["willingness_to_answer"])
        self.assertGreater(reserved["embarrassment"], active["embarrassment"])

    def test_invalid_or_out_of_range_values_are_normalized(self):
        profile = PROFILES_BY_ID["typical"]
        state = StudentState(
            role_id=profile.id,
            engagement_state={"attention": 2, "confidence": "bad"},
        )

        ensure_engagement_state(profile, state)

        self.assertEqual(state.engagement_state["attention"], 1.0)
        self.assertEqual(state.engagement_state["confidence"], 0.0)
        self.assertIn("frustration", state.engagement_state)

    def test_confirmed_learning_raises_confidence_and_lowers_frustration(self):
        profile = PROFILES_BY_ID["typical"]
        state = StudentState(role_id=profile.id)
        ensure_engagement_state(profile, state)
        before = dict(state.engagement_state)

        result = update_engagement_after_response(
            profile,
            state,
            before,
            {"status": "confirmed", "applied": True},
            "on_task",
            guarded=False,
        )

        self.assertGreater(result["after"]["confidence"], before["confidence"])
        self.assertLess(result["after"]["frustration"], before["frustration"])


if __name__ == "__main__":
    unittest.main()
