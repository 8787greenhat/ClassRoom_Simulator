from __future__ import annotations

from .models import StudentProfile, StudentState


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


def plan_student_behavior(
    profile: StudentProfile,
    state: StudentState,
    teacher_message: str,
) -> str:
    """Choose an observable behavior without changing the student's age or role."""
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
