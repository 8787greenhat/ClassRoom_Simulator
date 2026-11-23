from __future__ import annotations

from copy import deepcopy

from .models import StudentProfile, StudentState


DENSITY_CONCEPTS = (
    "mass",
    "volume",
    "density_ratio",
    "material_invariance",
    "unit_conversion",
)

CONCEPT_LABELS = {
    "mass": "質量",
    "volume": "體積",
    "density_ratio": "密度是質量與體積的比值",
    "material_invariance": "同材料切割前後密度不變",
    "unit_conversion": "密度單位換算",
}

MISCONCEPTION_BELIEFS = (
    "heavier_means_denser",
    "smaller_piece_less_dense",
)

BELIEF_LABELS = {
    "heavier_means_denser": "越重就一定越密",
    "smaller_piece_less_dense": "同材料切小後密度會變小",
}

PRIMARY_BELIEF_BY_ROLE = {
    "typical": "heavier_means_denser",
    "misconception": "heavier_means_denser",
    "reserved": "smaller_piece_less_dense",
}

ROLE_INITIAL_MASTERY = {
    "active": {"mass": 3, "volume": 3, "density_ratio": 2, "material_invariance": 2, "unit_conversion": 1},
    "typical": {"mass": 2, "volume": 2, "density_ratio": 1, "material_invariance": 1, "unit_conversion": 0},
    "misconception": {"mass": 2, "volume": 1, "density_ratio": 0, "material_invariance": 1, "unit_conversion": 0},
    "reserved": {"mass": 1, "volume": 1, "density_ratio": 0, "material_invariance": 0, "unit_conversion": 0},
    "distracted": {"mass": 1, "volume": 1, "density_ratio": 0, "material_invariance": 0, "unit_conversion": 0},
}

ROLE_INITIAL_BELIEFS = {
    "active": {},
    "typical": {"heavier_means_denser": 1},
    "misconception": {"heavier_means_denser": 3},
    "reserved": {"smaller_piece_less_dense": 1},
    "distracted": {},
}


def _clamp_level(value: object) -> int:
    try:
        return max(0, min(3, int(value)))
    except (TypeError, ValueError):
        return 0


def initial_concept_state(
    profile: StudentProfile,
    misconception_strength: int | None = None,
) -> tuple[dict[str, int], dict[str, int]]:
    mastery = deepcopy(ROLE_INITIAL_MASTERY[profile.id])
    beliefs = deepcopy(ROLE_INITIAL_BELIEFS[profile.id])
    primary = PRIMARY_BELIEF_BY_ROLE.get(profile.id)
    if primary is not None and misconception_strength is not None:
        beliefs[primary] = _clamp_level(misconception_strength)
    return mastery, beliefs


def ensure_concept_state(profile: StudentProfile, state: StudentState) -> None:
    default_mastery, default_beliefs = initial_concept_state(
        profile,
        state.misconception_strength,
    )
    normalized_mastery = {
        concept: _clamp_level(state.concept_mastery.get(concept, default_mastery[concept]))
        for concept in DENSITY_CONCEPTS
    }
    normalized_beliefs = {
        belief: _clamp_level(state.misconception_beliefs.get(belief, default_beliefs.get(belief, 0)))
        for belief in MISCONCEPTION_BELIEFS
        if belief in state.misconception_beliefs or belief in default_beliefs
    }
    state.concept_mastery = normalized_mastery
    state.misconception_beliefs = normalized_beliefs
    _sync_legacy_strength(profile, state)


def _sync_legacy_strength(profile: StudentProfile, state: StudentState) -> None:
    primary = PRIMARY_BELIEF_BY_ROLE.get(profile.id)
    if primary is not None:
        state.misconception_strength = state.misconception_beliefs.get(primary, 0)


def classify_teacher_evidence(message: str) -> dict:
    mass = any(term in message for term in ("質量", "重量"))
    volume = any(term in message for term in ("體積", "占空間", "大小"))
    ratio_relation = any(
        term in message
        for term in ("除以", "比值", "同時看", "同時考慮", "還要看", "不能只看")
    )
    material = any(term in message for term in ("同一材料", "同種材料", "同一種材料"))
    cutting = any(term in message for term in ("切割", "切成", "切小", "小塊"))
    invariant = "密度" in message and any(
        term in message for term in ("密度不變", "密度一樣", "密度相同", "不會改變")
    )
    unit = any(term in message for term in ("g/cm", "kg/m", "克每立方", "公斤每立方", "單位換算"))
    has_check = any(
        term in message
        for term in ("請舉例", "舉個例", "再說一次", "用自己的話", "對不對", "試著說", "你能說", "說說看", "為什麼")
    )

    concepts: list[str] = []
    if mass and volume and ratio_relation:
        concepts.extend(("mass", "volume", "density_ratio"))
    else:
        if any(term in message for term in ("質量是", "質量表示", "重量不是質量")):
            concepts.append("mass")
        if any(term in message for term in ("體積是", "體積表示", "占多少空間")):
            concepts.append("volume")
    if material and cutting and invariant:
        concepts.append("material_invariance")
    if unit:
        concepts.append("unit_conversion")

    targeted_beliefs: list[str] = []
    corrects_weight_belief = any(
        term in message
        for term in ("不能只看質量", "不能只看重量", "質量大不代表密度大", "重量大不代表密度大")
    )
    if corrects_weight_belief and volume and ratio_relation:
        targeted_beliefs.append("heavier_means_denser")
    if material and cutting and invariant:
        targeted_beliefs.append("smaller_piece_less_dense")

    return {
        "evidence_concepts": list(dict.fromkeys(concepts)),
        "targeted_beliefs": targeted_beliefs,
        "understanding_check": has_check,
    }


def stage_teacher_evidence(
    state: StudentState,
    profile: StudentProfile,
    message: str,
) -> dict:
    ensure_concept_state(profile, state)
    evidence = classify_teacher_evidence(message)
    pending = bool(
        evidence["understanding_check"]
        and (evidence["evidence_concepts"] or evidence["targeted_beliefs"])
    )
    return {
        **evidence,
        "student_demonstration": {
            "demonstrated_concepts": [],
            "demonstrated_beliefs": [],
        },
        "mastery_changes": {},
        "belief_changes": {},
        "response_eligible": None,
        "confirmation_source": None,
        "status": "pending_student_response" if pending else "no_actionable_evidence",
        "applied": False,
    }


def classify_student_demonstration(response: str, evidence: dict) -> dict:
    mass = any(term in response for term in ("質量", "重量", "重不重"))
    volume = any(term in response for term in ("體積", "占多少空間", "大小"))
    ratio_relation = any(
        term in response
        for term in ("除以", "比值", "同時看", "同時考慮", "還要看", "不能只看", "不只看")
    )
    material = any(term in response for term in ("同一材料", "同種材料", "同一種材料"))
    cutting = any(term in response for term in ("切割", "切成", "切小", "小塊"))
    invariant = "密度" in response and any(
        term in response for term in ("不變", "一樣", "相同", "不會改變")
    )
    invariant = invariant and not any(
        term in response for term in ("不一樣", "不相同", "會改變", "變小", "變大")
    )
    unit = any(term in response for term in ("g/cm", "kg/m", "克每立方", "公斤每立方", "單位"))

    demonstrated: list[str] = []
    for concept in evidence.get("evidence_concepts", []):
        success = {
            "mass": mass,
            "volume": volume,
            "density_ratio": mass and volume and ratio_relation,
            "material_invariance": material and cutting and invariant,
            "unit_conversion": unit,
        }.get(concept, False)
        if success:
            demonstrated.append(concept)

    beliefs: list[str] = []
    retains_weight_belief = any(
        term in response
        for term in ("還是覺得", "比較重就比較密", "重的比較密", "不太相信", "不相信")
    )
    if (
        "heavier_means_denser" in evidence.get("targeted_beliefs", [])
        and "density_ratio" in demonstrated
        and not retains_weight_belief
    ):
        beliefs.append("heavier_means_denser")
    if (
        "smaller_piece_less_dense" in evidence.get("targeted_beliefs", [])
        and "material_invariance" in demonstrated
    ):
        beliefs.append("smaller_piece_less_dense")
    return {
        "demonstrated_concepts": demonstrated,
        "demonstrated_beliefs": beliefs,
    }


def confirm_learning_from_response(
    state: StudentState,
    profile: StudentProfile,
    staged_evidence: dict,
    response: str,
    *,
    response_eligible: bool,
    confirmation_source: str,
) -> dict:
    ensure_concept_state(profile, state)
    evidence = {
        "evidence_concepts": list(staged_evidence.get("evidence_concepts", [])),
        "targeted_beliefs": list(staged_evidence.get("targeted_beliefs", [])),
        "understanding_check": bool(staged_evidence.get("understanding_check")),
    }
    demonstration = classify_student_demonstration(response, evidence)
    mastery_changes: dict[str, dict[str, int]] = {}
    belief_changes: dict[str, dict[str, int]] = {}

    actionable = evidence["understanding_check"] and bool(
        evidence["evidence_concepts"] or evidence["targeted_beliefs"]
    )
    if response_eligible and actionable:
        for concept in demonstration["demonstrated_concepts"]:
            before = state.concept_mastery[concept]
            after = min(3, before + 1)
            if after != before:
                state.concept_mastery[concept] = after
                mastery_changes[concept] = {"before": before, "after": after}

        for belief in demonstration["demonstrated_beliefs"]:
            if belief not in state.misconception_beliefs:
                continue
            before = state.misconception_beliefs[belief]
            after = max(0, before - 1)
            if after != before:
                state.misconception_beliefs[belief] = after
                belief_changes[belief] = {"before": before, "after": after}

    _sync_legacy_strength(profile, state)
    if not actionable:
        status = "no_actionable_evidence"
    elif not response_eligible:
        status = "ineligible_response_source"
    elif demonstration["demonstrated_concepts"] or demonstration["demonstrated_beliefs"]:
        status = "confirmed"
    else:
        status = "not_confirmed"
    return {
        **evidence,
        "student_demonstration": demonstration,
        "mastery_changes": mastery_changes,
        "belief_changes": belief_changes,
        "response_eligible": response_eligible,
        "confirmation_source": confirmation_source,
        "status": status,
        "applied": bool(mastery_changes or belief_changes),
    }


def apply_teacher_evidence(
    state: StudentState,
    profile: StudentProfile,
    message: str,
) -> dict:
    """Compatibility wrapper: teacher evidence is staged and never learns by itself."""
    return stage_teacher_evidence(state, profile, message)
