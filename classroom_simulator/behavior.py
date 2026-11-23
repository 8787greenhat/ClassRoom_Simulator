from __future__ import annotations

from .models import BehaviorPlan, StudentProfile, StudentState


BEHAVIOR_TYPES = (
    "on_task",
    "confused",
    "distracted",
    "off_topic",
    "imaginative",
    "redirected",
)

DENSITY_TERMS = ("密度", "質量", "體積", "重量", "切割", "材料")

BEHAVIOR_INSTRUCTIONS = {
    "on_task": "直接回應教師的具體問題，但維持角色原本的程度與迷思。",
    "confused": "指出自己卡住的地方並提出一個簡短問題。",
    "distracted": "坦白剛才沒跟上，請教師重述題目，不可假裝聽懂。",
    "off_topic": "先說一句短而自然的生活岔題，再承認沒有聽到問題；不可長篇胡鬧。",
    "imaginative": "提出一個天馬行空但仍能連回密度的生活或科幻想像。",
    "redirected": "被明確點名後回到教師的具體問題，嘗試回答但可以不完整。",
}

BEHAVIOR_FALLBACKS = {
    "distracted": ("老師，我剛剛有點沒跟上，可以再說一次問題嗎？", "confused"),
    "off_topic": ("老師，我剛剛在想午餐的布丁，前面那題沒有聽到。", "neutral"),
    "imaginative": ("如果把一顆星球壓成彈珠那麼小，它的密度會不會超大？", "curious"),
    "redirected": ("如果質量一樣，是不是體積比較小的密度比較大？", "confused"),
}

ROLE_RESPONSE_EXAMPLES = {
    "active": (
        ("同一種材料切小塊後會怎樣？", "密度不會變，那如果溫度變了也一樣嗎？"),
        ("質量相同時怎麼比較密度？", "要看體積吧？體積比較小的為什麼會比較密？"),
    ),
    "typical": (
        ("密度公式是什麼？", "我記得是質量除以體積，但單位那邊還有點亂。"),
        ("比較重就一定比較密嗎？", "好像不一定，可是我不太確定還要比較哪一個。"),
    ),
    "misconception": (
        ("重的物體一定比較密嗎？", "可是拿起來比較重，感覺就應該比較密吧？"),
        ("只看重量可以判斷密度嗎？", "我還是不太相信，能不能拿兩個東西實際比給我看？"),
    ),
    "reserved": (
        ("切小塊後密度會變嗎？", "我不太確定……變小塊以後，密度不會也變小嗎？"),
        ("你覺得哪個比較密？", "可能是鐵吧……但我不知道要怎麼說理由。"),
    ),
    "distracted": (
        ("小宇，你有在聽嗎？", "蛤，我剛剛沒跟上，可以再說一次題目嗎？"),
        ("小宇，質量相同時怎麼比較密度？", "要看體積嗎？體積小的應該比較密吧。"),
    ),
}


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
) -> str:
    if profile.id != "distracted":
        return "on_task"

    message = teacher_message.strip()
    named = profile.name in message
    concrete_topic = any(term in message for term in DENSITY_TERMS)
    generic_recall = any(
        marker in message for marker in ("有在聽", "剛才的問題", "剛剛的問題")
    )

    if generic_recall and not concrete_topic:
        return "distracted"

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
    behavior_type = _choose_behavior_type(profile, state, teacher_message)
    shared_forbidden = ("自稱是 AI", "評價教師教得好不好", "使用教師或助理口吻")

    if behavior_type == "distracted":
        return BehaviorPlan(
            behavior_type=behavior_type,
            understanding="沒有聽清楚教師剛才的具體問題",
            intent="坦白沒跟上並請教師重述問題",
            confidence="low",
            emotion_hint="confused",
            misconception=None,
            style=("口語化", "短句", "帶一點尷尬但不胡鬧"),
            required_meanings=("沒跟上", "請求重述問題"),
            forbidden_meanings=shared_forbidden + ("假裝知道題目",),
        )
    if behavior_type == "off_topic":
        return BehaviorPlan(
            behavior_type=behavior_type,
            understanding="注意力暫時離開課堂，沒有聽完整問題",
            intent="先自然岔題一句，再承認沒聽到問題",
            confidence="low",
            emotion_hint="neutral",
            misconception=None,
            style=("口語化", "短句", "岔題後立刻收回"),
            required_meanings=("生活岔題", "承認漏聽"),
            forbidden_meanings=shared_forbidden + ("長篇胡鬧",),
        )
    if behavior_type == "imaginative":
        return BehaviorPlan(
            behavior_type=behavior_type,
            understanding="掌握部分密度概念，但注意力轉向生活或科幻想像",
            intent="提出一個能連回密度的想像問題",
            confidence="medium",
            emotion_hint="curious",
            misconception=None,
            style=("口語化", "有想像力", "仍與密度相關"),
            required_meanings=("假設或想像", "連回密度"),
            forbidden_meanings=shared_forbidden + ("完全離題",),
        )
    if behavior_type == "redirected":
        return BehaviorPlan(
            behavior_type=behavior_type,
            understanding="被點名後重新注意教師的具體問題",
            intent="嘗試回答核心概念，允許答案不完整",
            confidence="medium-low",
            emotion_hint="confused",
            misconception=None,
            style=("口語化", "簡短", "像剛回神的學生"),
            required_meanings=("回應教師的具體問題",),
            forbidden_meanings=shared_forbidden + ("繼續無關岔題",),
        )

    role_plans = {
        "active": ("大致理解當前概念", "追問原因、條件或生活應用", "high", "curious"),
        "typical": ("只理解部分概念", "說出目前理解並指出一個卡住處", "medium-low", "confused"),
        "misconception": (
            "仍以重量直覺理解密度" if state.misconception_strength >= 2 else "開始比較質量與體積",
            "維持目前理由並要求具體反例" if state.misconception_strength >= 2 else "用自己的話確認新理解",
            "medium-high" if state.misconception_strength >= 2 else "medium-low",
            "confused",
        ),
        "reserved": ("可能想到部分答案但不敢確定", "被點名後簡短且保留地回答", "low", "confused"),
        "distracted": ("聽到具體問題並暫時回到課堂", "用不完整但相關的方式回答", "medium-low", "neutral"),
    }
    understanding, intent, confidence, emotion_hint = role_plans[profile.id]
    misconception = profile.misconception if state.misconception_strength > 0 else None
    return BehaviorPlan(
        behavior_type=behavior_type,
        understanding=understanding,
        intent=intent,
        confidence=confidence,
        emotion_hint=emotion_hint,
        misconception=misconception,
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
