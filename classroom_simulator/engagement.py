from __future__ import annotations

from copy import deepcopy

from .models import StudentProfile, StudentState


ENGAGEMENT_KEYS = (
    "attention",
    "willingness_to_answer",
    "frustration",
    "embarrassment",
    "confidence",
)

ROLE_INITIAL_ENGAGEMENT = {
    "active": {
        "attention": 0.85,
        "willingness_to_answer": 0.90,
        "frustration": 0.15,
        "embarrassment": 0.10,
        "confidence": 0.75,
    },
    "typical": {
        "attention": 0.65,
        "willingness_to_answer": 0.55,
        "frustration": 0.30,
        "embarrassment": 0.20,
        "confidence": 0.50,
    },
    "misconception": {
        "attention": 0.70,
        "willingness_to_answer": 0.65,
        "frustration": 0.30,
        "embarrassment": 0.15,
        "confidence": 0.70,
    },
    "reserved": {
        "attention": 0.65,
        "willingness_to_answer": 0.18,
        "frustration": 0.35,
        "embarrassment": 0.65,
        "confidence": 0.25,
    },
    "distracted": {
        "attention": 0.30,
        "willingness_to_answer": 0.40,
        "frustration": 0.20,
        "embarrassment": 0.15,
        "confidence": 0.40,
    },
}

DENSITY_TERMS = ("密度", "質量", "體積", "重量", "切割", "材料")


def _clamp_score(value: object) -> float:
    try:
        return round(max(0.0, min(1.0, float(value))), 2)
    except (TypeError, ValueError):
        return 0.0


def initial_engagement_state(profile: StudentProfile) -> dict[str, float]:
    return deepcopy(ROLE_INITIAL_ENGAGEMENT[profile.id])


def ensure_engagement_state(profile: StudentProfile, state: StudentState) -> None:
    defaults = ROLE_INITIAL_ENGAGEMENT[profile.id]
    state.engagement_state = {
        key: _clamp_score(state.engagement_state.get(key, defaults[key]))
        for key in ENGAGEMENT_KEYS
    }


def project_engagement_for_turn(
    profile: StudentProfile,
    state: StudentState,
    teacher_message: str,
) -> dict[str, float]:
    ensure_engagement_state(profile, state)
    projected = dict(state.engagement_state)
    named = profile.name in teacher_message
    concrete = any(term in teacher_message for term in DENSITY_TERMS)
    asks_question = any(mark in teacher_message for mark in ("？", "?", "為什麼", "說說看", "再說一次", "用自己的話"))
    generic_recall = any(mark in teacher_message for mark in ("有在聽", "剛才的問題", "剛剛的問題"))

    if named:
        projected["attention"] += 0.15
        projected["willingness_to_answer"] += 0.20
    elif len(teacher_message) >= 45:
        projected["attention"] -= 0.10
    if asks_question and concrete:
        projected["willingness_to_answer"] += 0.05
    if generic_recall and profile.id == "distracted":
        projected["embarrassment"] += 0.15
        projected["willingness_to_answer"] -= 0.05

    return {key: _clamp_score(projected[key]) for key in ENGAGEMENT_KEYS}


def update_engagement_after_response(
    profile: StudentProfile,
    state: StudentState,
    turn_state: dict[str, float],
    learning_update: dict,
    behavior_type: str,
    *,
    guarded: bool,
) -> dict:
    ensure_engagement_state(profile, state)
    before = dict(state.engagement_state)
    after = {key: _clamp_score(turn_state.get(key, before[key])) for key in ENGAGEMENT_KEYS}
    status = learning_update.get("status")

    if status == "confirmed":
        after["confidence"] += 0.15
        after["frustration"] -= 0.15
        after["embarrassment"] -= 0.05
    elif status == "not_confirmed":
        after["confidence"] -= 0.05
        after["frustration"] += 0.10
    if guarded:
        after["confidence"] -= 0.05
        after["frustration"] += 0.10
    if behavior_type == "silent":
        after["willingness_to_answer"] -= 0.05
        after["embarrassment"] += 0.10
    elif behavior_type == "hesitant":
        after["embarrassment"] += 0.05

    state.engagement_state = {key: _clamp_score(after[key]) for key in ENGAGEMENT_KEYS}
    changes = {
        key: {"before": before[key], "after": state.engagement_state[key]}
        for key in ENGAGEMENT_KEYS
        if before[key] != state.engagement_state[key]
    }
    return {
        "before": before,
        "turn_state": {key: _clamp_score(turn_state[key]) for key in ENGAGEMENT_KEYS},
        "after": dict(state.engagement_state),
        "changes": changes,
    }
