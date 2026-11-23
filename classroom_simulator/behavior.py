from __future__ import annotations

from dataclasses import dataclass

from .engagement import project_engagement_for_turn
from .learning import CONCEPT_LABELS, classify_teacher_evidence, ensure_concept_state
from .models import BehaviorPlan, StudentProfile, StudentState


BEHAVIOR_TYPES = (
    "on_task",
    "confused",
    "distracted",
    "off_topic",
    "imaginative",
    "redirected",
    "silent",
    "hesitant",
)

DENSITY_TERMS = ("密度", "質量", "體積", "重量", "切割", "材料")

TEACHER_MOVES = (
    "definition",
    "comparison",
    "explanation",
    "application",
    "misconception_check",
    "recall",
    "generic",
)


@dataclass(frozen=True)
class RoleResponseExample:
    teacher_move: str
    teacher: str
    student: str

BEHAVIOR_INSTRUCTIONS = {
    "on_task": "直接回應教師的具體問題，但維持角色原本的程度與迷思。",
    "confused": "指出自己卡住的地方並提出一個簡短問題。",
    "distracted": "坦白剛才沒跟上，請教師重述題目，不可假裝聽懂。",
    "off_topic": "先說一句短而自然的生活岔題，再承認沒有聽到問題；不可長篇胡鬧。",
    "imaginative": "提出一個天馬行空但仍能連回密度的生活或科幻想像。",
    "redirected": "被明確點名後回到教師的具體問題，嘗試回答但可以不完整。",
    "silent": "當輪不作口頭回答，只輸出省略號，不可補充解釋。",
    "hesitant": "簡短說不知道或不確定；可以指出卡住處，但不可假裝理解。",
}

BEHAVIOR_FALLBACKS = {
    "distracted": ("老師，我剛剛有點沒跟上，可以再說一次問題嗎？", "confused"),
    "off_topic": ("老師，我剛剛在想午餐的布丁，前面那題沒有聽到。", "neutral"),
    "imaginative": ("如果把一顆星球壓成彈珠那麼小，它的密度會不會超大？", "curious"),
    "redirected": ("如果質量一樣，是不是體積比較小的密度比較大？", "confused"),
    "silent": ("……", "embarrassed"),
    "hesitant": ("我不知道……我還沒想清楚。", "embarrassed"),
}

ROLE_RESPONSE_EXAMPLES = {
    "active": (
        RoleResponseExample("definition", "密度是什麼？", "是不是要一起看質量和體積？那為什麼要用除的？"),
        RoleResponseExample("comparison", "質量相同時怎麼比較密度？", "要看體積吧？體積比較小的為什麼會比較密？"),
    ),
    "typical": (
        RoleResponseExample("definition", "密度是什麼？", "我記得跟質量和體積都有關，可是公式有點忘了。"),
        RoleResponseExample("misconception_check", "比較重就一定比較密嗎？", "好像不一定，可是我不太確定還要比較哪一個。"),
    ),
    "misconception": (
        RoleResponseExample("definition", "密度是什麼？", "我覺得就是東西有多重吧，越重應該越密。"),
        RoleResponseExample("misconception_check", "只看重量可以判斷密度嗎？", "我還是不太相信，能不能拿兩個東西實際比給我看？"),
    ),
    "reserved": (
        RoleResponseExample("definition", "密度是什麼？", "是不是跟重不重有關……我不太確定。"),
        RoleResponseExample("comparison", "你覺得哪個比較密？", "可能是鐵吧……但我不知道要怎麼說理由。"),
    ),
    "distracted": (
        RoleResponseExample("recall", "小宇，你有在聽嗎？", "蛤，我剛剛沒跟上，可以再說一次題目嗎？"),
        RoleResponseExample("definition", "小宇，密度是什麼？", "密度喔……我只記得好像跟重不重有關，其他忘了。"),
    ),
}


def classify_teacher_move(teacher_message: str) -> str:
    """Classify what kind of response the teacher is asking for this turn."""
    message = teacher_message.strip()
    concrete_topic = any(term in message for term in DENSITY_TERMS)
    if any(marker in message for marker in ("有在聽", "剛才的問題", "剛剛的問題")) and not concrete_topic:
        return "recall"
    if any(marker in message for marker in ("是什麼", "什麼是", "什麼叫", "意思是", "怎麼定義")):
        return "definition"
    if any(marker in message for marker in ("一定", "只看重量", "同意嗎", "對不對")) or (
        "重量" in message and any(marker in message for marker in ("同意", "不能決定"))
    ):
        return "misconception_check"
    if any(marker in message for marker in ("怎麼比較", "哪個比較", "哪一個比較", "相同", "一樣")):
        return "comparison"
    if any(marker in message for marker in ("為什麼", "原因", "怎麼解釋")):
        return "explanation"
    if any(marker in message for marker in ("舉例", "例子", "生活中", "應用")):
        return "application"
    return "generic"


def _response_grounding(teacher_message: str, teacher_move: str) -> tuple[str, tuple[str, ...]]:
    focuses = {
        "definition": "直接回答或猜測密度的意思，不可改答成比較題",
        "comparison": "只使用教師明示的比較條件回答要比較什麼",
        "explanation": "回應教師詢問的原因；不懂時指出因果卡在哪裡",
        "application": "提供或討論一個和密度有關的例子",
        "misconception_check": "依目前信念表示是否同意，並給出學生程度的理由",
        "recall": "承認是否聽到問題；沒有題目內容時請教師重述",
        "generic": "只回應教師這一輪明示的內容",
    }
    assumptions = []
    if not any(marker in teacher_message for marker in ("質量相同", "同質量", "一樣重")):
        assumptions.append("質量相同")
    if not any(marker in teacher_message for marker in ("體積相同", "同體積", "一樣大")):
        assumptions.append("體積相同")
    return focuses[teacher_move], tuple(assumptions)


def response_examples_for(profile_id: str, teacher_move: str) -> tuple[RoleResponseExample, ...]:
    """Return only examples matching the current teacher move."""
    return tuple(
        example
        for example in ROLE_RESPONSE_EXAMPLES[profile_id]
        if example.teacher_move == teacher_move
    )


def teacher_alignment_failures(
    teacher_message: str,
    teacher_move: str,
    response: str,
) -> list[str]:
    """Find unsupported comparison conditions introduced by a student response."""
    failures: list[str] = []
    same_mass_in_question = any(
        marker in teacher_message for marker in ("質量相同", "同質量", "一樣重")
    )
    same_volume_in_question = any(
        marker in teacher_message for marker in ("體積相同", "同體積", "一樣大")
    )
    if not same_mass_in_question and any(
        marker in response for marker in ("質量相同", "同質量", "一樣重")
    ):
        failures.append("adds_unstated_same_mass_condition")
    if not same_volume_in_question and any(
        marker in response for marker in ("體積相同", "同體積", "一樣大")
    ):
        failures.append("adds_unstated_same_volume_condition")
    if teacher_move == "definition" and any(
        marker in response for marker in ("體積小的密度", "體積比較小", "哪個比較密")
    ):
        failures.append("answers_comparison_instead_of_definition")
    return failures


def contextual_fallback_response(profile_id: str, teacher_move: str) -> tuple[str, str]:
    """Provide a safe, role-shaped response when both model attempts drift."""
    if teacher_move == "definition":
        responses = {
            "active": ("密度是不是要一起看質量和體積？我想知道為什麼要用除的。", "curious"),
            "typical": ("我記得密度跟質量和體積都有關，可是公式有點忘了。", "confused"),
            "misconception": ("我覺得密度就是東西有多重，越重應該就越密吧？", "confused"),
            "reserved": ("是不是跟東西重不重有關……我不太確定。", "confused"),
            "distracted": ("密度喔……我只記得好像跟重不重有關，其他忘了。", "confused"),
        }
        return responses[profile_id]
    example = next(iter(response_examples_for(profile_id, teacher_move)), None)
    if example:
        return example.student, "confused"
    return "我不太確定老師現在要我回答哪一部分。", "confused"


def enforce_behavior_consistency(
    behavior_type: str,
    response: str,
    emotion: str,
) -> tuple[str, str, bool]:
    """Ensure the visible response matches the behavior label assigned by the system."""
    markers = {
        "distracted": ("沒跟上", "再說一次", "再講一遍", "什麼問題", "哪個問題"),
        "off_topic": ("午餐", "布丁", "遊戲", "下課", "球賽", "手機"),
        "imaginative": ("如果", "假如", "想像", "星球", "縮小", "變成"),
        "redirected": DENSITY_TERMS,
        "silent": ("……", "..."),
        "hesitant": ("不知道", "不確定", "不敢", "還沒想清楚"),
    }
    expected_markers = markers.get(behavior_type)
    if not expected_markers or any(marker in response for marker in expected_markers):
        return response, emotion, False

    fallback = BEHAVIOR_FALLBACKS[behavior_type]
    return fallback[0], fallback[1], True


def _choose_behavior_type(
    profile: StudentProfile,
    state: StudentState,
    teacher_message: str,
    engagement_state: dict[str, float],
) -> str:
    message = teacher_message.strip()
    named = profile.name in message
    concrete_topic = any(term in message for term in DENSITY_TERMS)
    asks_question = any(mark in message for mark in ("？", "?", "為什麼", "說說看", "再說一次", "用自己的話"))
    generic_recall = any(
        marker in message for marker in ("有在聽", "剛才的問題", "剛剛的問題")
    )

    if profile.id == "distracted" and generic_recall and not concrete_topic:
        return "distracted"

    if engagement_state["willingness_to_answer"] <= 0.20 and not named:
        return "silent"
    if (
        engagement_state["confidence"] <= 0.25
        or engagement_state["frustration"] >= 0.70
        or engagement_state["embarrassment"] >= 0.80
    ) and (named or asks_question):
        return "hesitant"

    if profile.id != "distracted":
        return "on_task"

    if named and concrete_topic:
        return "redirected" if state.participation_count > 0 else "on_task"

    if len(message) >= 45 and not named:
        return "imaginative" if state.participation_count % 2 == 0 else "off_topic"

    if not named and not concrete_topic:
        return "off_topic"

    return "on_task"


def build_behavior_plan(
    profile: StudentProfile,
    state: StudentState,
    teacher_message: str,
) -> BehaviorPlan:
    """Describe the student's hidden turn intent without scripting the utterance."""
    ensure_concept_state(profile, state)
    engagement_state = project_engagement_for_turn(profile, state, teacher_message)
    behavior_type = _choose_behavior_type(profile, state, teacher_message, engagement_state)
    teacher_move = classify_teacher_move(teacher_message)
    response_focus, forbidden_assumptions = _response_grounding(teacher_message, teacher_move)
    shared_forbidden = ("自稱是 AI", "評價教師教得好不好", "使用教師或助理口吻")
    weak_concepts = [
        CONCEPT_LABELS[concept]
        for concept, level in state.concept_mastery.items()
        if level <= 1
    ]
    knowledge_context = "尚未穩定：" + "、".join(weak_concepts or ["無"])
    state_payload = {
        "concept_mastery": dict(state.concept_mastery),
        "misconception_beliefs": dict(state.misconception_beliefs),
        "engagement_state": engagement_state,
        "teacher_move": teacher_move,
        "response_focus": response_focus,
        "forbidden_assumptions": forbidden_assumptions,
    }

    if behavior_type == "silent":
        return BehaviorPlan(
            behavior_type=behavior_type,
            understanding=f"當下不願公開回答；{knowledge_context}",
            intent="保持沉默，不用語句假裝回答",
            confidence="low",
            emotion_hint="embarrassed",
            misconception=None,
            **state_payload,
            style=("只輸出省略號",),
            required_meanings=("沉默",),
            forbidden_meanings=shared_forbidden + ("解釋答案",),
        )
    if behavior_type == "hesitant":
        return BehaviorPlan(
            behavior_type=behavior_type,
            understanding=f"可能只想到一部分，但沒有把握；{knowledge_context}",
            intent="簡短表示不知道或不確定",
            confidence="low",
            emotion_hint="embarrassed",
            misconception=profile.misconception if any(state.misconception_beliefs.values()) else None,
            **state_payload,
            style=(profile.speaking_style, "短句", "保留"),
            required_meanings=("不知道或不確定",),
            forbidden_meanings=shared_forbidden + ("假裝完全理解",),
        )

    if behavior_type == "distracted":
        return BehaviorPlan(
            behavior_type=behavior_type,
            understanding=f"沒有聽清楚教師剛才的具體問題；{knowledge_context}",
            intent="坦白沒跟上並請教師重述問題",
            confidence="low",
            emotion_hint="confused",
            misconception=None,
            **state_payload,
            style=("口語化", "短句", "帶一點尷尬但不胡鬧"),
            required_meanings=("沒跟上", "請求重述問題"),
            forbidden_meanings=shared_forbidden + ("假裝知道題目",),
        )
    if behavior_type == "off_topic":
        return BehaviorPlan(
            behavior_type=behavior_type,
            understanding=f"注意力暫時離開課堂，沒有聽完整問題；{knowledge_context}",
            intent="先自然岔題一句，再承認沒聽到問題",
            confidence="low",
            emotion_hint="neutral",
            misconception=None,
            **state_payload,
            style=("口語化", "短句", "岔題後立刻收回"),
            required_meanings=("生活岔題", "承認漏聽"),
            forbidden_meanings=shared_forbidden + ("長篇胡鬧",),
        )
    if behavior_type == "imaginative":
        return BehaviorPlan(
            behavior_type=behavior_type,
            understanding=f"掌握部分密度概念，但注意力轉向生活或科幻想像；{knowledge_context}",
            intent="提出一個能連回密度的想像問題",
            confidence="medium",
            emotion_hint="curious",
            misconception=None,
            **state_payload,
            style=("口語化", "有想像力", "仍與密度相關"),
            required_meanings=("假設或想像", "連回密度"),
            forbidden_meanings=shared_forbidden + ("完全離題",),
        )
    if behavior_type == "redirected":
        return BehaviorPlan(
            behavior_type=behavior_type,
            understanding=f"被點名後重新注意教師的具體問題；{knowledge_context}",
            intent="嘗試回答核心概念，允許答案不完整",
            confidence="medium-low",
            emotion_hint="confused",
            misconception=None,
            **state_payload,
            style=("口語化", "簡短", "像剛回神的學生"),
            required_meanings=("回應教師的具體問題",),
            forbidden_meanings=shared_forbidden + ("繼續無關岔題",),
        )

    evidence = classify_teacher_evidence(teacher_message)
    asks_to_demonstrate = bool(
        evidence["understanding_check"]
        and "heavier_means_denser" in evidence["targeted_beliefs"]
    )
    role_plans = {
        "active": ("大致理解當前概念", "追問原因、條件或生活應用", "high", "curious"),
        "typical": ("只理解部分概念", "說出目前理解並指出一個卡住處", "medium-low", "confused"),
        "misconception": (
            "仍以重量直覺理解密度" if state.misconception_beliefs.get("heavier_means_denser", 0) >= 2 else "開始比較質量與體積",
            (
                "嘗試用自己的話解釋教師提供的反例"
                if asks_to_demonstrate
                else "維持目前理由並要求具體反例"
            ) if state.misconception_beliefs.get("heavier_means_denser", 0) >= 2 else "用自己的話確認新理解",
            "medium-high" if state.misconception_beliefs.get("heavier_means_denser", 0) >= 2 else "medium-low",
            "confused",
        ),
        "reserved": ("可能想到部分答案但不敢確定", "被點名後簡短且保留地回答", "low", "confused"),
        "distracted": ("聽到具體問題並暫時回到課堂", "用不完整但相關的方式回答", "medium-low", "neutral"),
    }
    understanding, intent, confidence, emotion_hint = role_plans[profile.id]
    misconception = profile.misconception if any(state.misconception_beliefs.values()) else None
    return BehaviorPlan(
        behavior_type=behavior_type,
        understanding=f"{understanding}；{knowledge_context}",
        intent=intent,
        confidence=confidence,
        emotion_hint=emotion_hint,
        misconception=misconception,
        **state_payload,
        style=(profile.speaking_style, "國中生自然口吻", "一到兩句"),
        required_meanings=(intent,),
        forbidden_meanings=shared_forbidden,
    )


def plan_student_behavior(
    profile: StudentProfile,
    state: StudentState,
    teacher_message: str,
) -> str:
    """Backward-compatible behavior label used by existing callers and tests."""
    return build_behavior_plan(profile, state, teacher_message).behavior_type
