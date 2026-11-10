from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from abc import ABC, abstractmethod

from .behavior import (
    BEHAVIOR_INSTRUCTIONS,
    enforce_behavior_consistency,
    plan_student_behavior,
)
from .models import AgentReply, StudentProfile, StudentState


DENSITY_KNOWLEDGE = """
課程範圍：國中自然科「密度」。
- 密度 = 質量 / 體積，常用單位為 g/cm³ 或 kg/m³。
- 同一種均勻材料在相同條件下，切割前後密度不因大小改變。
- 質量大不代表密度一定大；必須同時考慮體積。
- 學生可以犯角色指定的錯誤，但不得引入範圍外的虛構事實。
""".strip()

DENSITY_PROMPT_VERSION = "density-v4.2"

INVALID_STUDENT_RESPONSES = frozenset(
    {"學生發言", "學生回答", "請填入學生發言", "response", "學生的回答"}
)


def normalize_student_response(response: str) -> str:
    """Normalize one classroom utterance and reject copied schema placeholders."""
    normalized = " ".join(response.split())
    if not normalized or normalized in INVALID_STUDENT_RESPONSES:
        raise ValueError("Ollama returned an empty or placeholder response")
    return normalized


def enforce_response_length(response: str, max_chars: int = 45) -> tuple[str, bool]:
    """Keep one visible utterance within the classroom limit and mark the rewrite."""
    if max_chars < 2:
        raise ValueError("max_chars must be at least 2")
    if len(response) <= max_chars:
        return response, False

    sentence_endings = "。！？?"
    usable_endings = [
        index + 1
        for index, character in enumerate(response[:max_chars])
        if character in sentence_endings
    ]
    if usable_endings:
        return response[: usable_endings[-1]], True

    shortened = response[: max_chars - 1].rstrip("，、；：,;: ") + "…"
    return shortened, True

ROLE_BEHAVIOR_RULES = {
    "active": "理解後要追問原因、條件或生活應用，不要只重複教師的句子。",
    "typical": "如果還不懂，要指出卡住的概念；不要為了配合教師而假裝完全理解。",
    "misconception": "迷思強度大於等於 2 時，維持『比較重通常就比較密』的想法，並要求具體反例；不可先同意教師、道謝或直接說出完整正解。",
    "reserved": "即使想到答案，也先用不確定、簡短的語氣回答，避免像熟練學生直接下結論。",
    "distracted": "若教師只問你有沒有在聽、卻沒有重述具體題目，要承認沒跟上並請教師重述；不可自行猜題或假裝聽懂。",
}


def enforce_role_consistency(
    profile: StudentProfile,
    state: StudentState,
    response: str,
    emotion: str,
    teacher_message: str = "",
) -> tuple[str, str, bool]:
    """Prevent a high-strength misconception role from agreeing too quickly."""
    if profile.id == "distracted":
        generic_recall_prompt = any(
            marker in teacher_message for marker in ("有在聽", "剛才的問題", "剛剛的問題")
        )
        concrete_topic = any(
            marker in teacher_message for marker in ("密度", "質量", "體積", "重量", "切割")
        )
        asks_for_context = any(
            marker in response for marker in ("沒跟上", "再說一次", "再講一遍", "什麼問題", "哪個問題")
        )
        if generic_recall_prompt and not concrete_topic and not asks_for_context:
            return "老師，我剛剛有點沒跟上，可以再說一次問題嗎？", "confused", True

    if profile.id != "misconception" or state.misconception_strength < 2:
        return response, emotion, False

    premature_correction = (
        "不一定",
        "不能只看",
        "還要看體積",
        "我同意",
        "我接受",
        "沒有直接關係",
        "謝謝你的提醒",
        "你說得對",
        "我懂了",
        "我明白了",
        "原來如此",
        "密度是質量除以體積",
        "謝謝老師",
        "謝謝",
    )
    stubborn_markers = (
        "可是",
        "為什麼不能",
        "感覺就比較密",
        "我還是覺得",
        "還是不懂",
        "不太相信",
    )
    if any(marker in response for marker in premature_correction) and not any(
        marker in response for marker in stubborn_markers
    ):
        guarded = "可是比較重的東西摸起來通常也比較扎實，我還是不懂為什麼不能只看重量。"
        return guarded, "confused", True
    return response, emotion, False


class LLMProvider(ABC):
    name = "unknown"

    @abstractmethod
    def reply(
        self,
        profile: StudentProfile,
        state: StudentState,
        teacher_message: str,
        topic: str,
        objective: str,
    ) -> AgentReply:
        raise NotImplementedError


class OllamaProvider(LLMProvider):
    name = "ollama"

    def __init__(self, base_url: str | None = None, model: str | None = None, timeout: float = 45.0):
        self.base_url = (base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")).rstrip("/")
        self.model = model or os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
        self.timeout = timeout

    def available(self) -> bool:
        try:
            request = urllib.request.Request(f"{self.base_url}/api/tags", method="GET")
            with urllib.request.urlopen(request, timeout=1.2) as response:
                return response.status == 200
        except (OSError, urllib.error.URLError):
            return False

    def reply(self, profile, state, teacher_message, topic, objective) -> AgentReply:
        behavior_type = plan_student_behavior(profile, state, teacher_message)
        system_prompt = f"""
你正在扮演國中學生「{profile.name}」，不可用教師或 AI 助理口吻回答。
個性：{profile.personality}
程度：{profile.ability_level}
參與程度：{profile.participation_level}
說話方式：{profile.speaking_style}
指定迷思：{profile.misconception or '無固定迷思'}
目前迷思強度：{state.misconception_strength}/3。
此角色本輪行為規則：{ROLE_BEHAVIOR_RULES[profile.id]}
本輪預期行為類型：{behavior_type}
本輪行為指示：{BEHAVIOR_INSTRUCTIONS[behavior_type]}

{DENSITY_KNOWLEDGE}

規則：
1. 回答必須像學生現場發言，只說一句、25 至 40 個中文字，絕對不可超過 45 字。
2. 迷思強度大於 0 時，不可因教師一次簡單提示就立刻完全改口。
3. 可以表示困惑、追問或反駁，但不要討好教師或評價教師表現。
4. 只輸出 JSON：{{"response":"實際的一句學生回答","emotion":"neutral|confused|curious|confident"}}；不可把「學生發言／學生回答」當成答案。
""".strip()
        memory = state.memory[-6:]
        messages = [{"role": "system", "content": system_prompt}]
        for item in memory:
            messages.append({"role": item["role"], "content": item["content"]})
        messages.append(
            {
                "role": "user",
                "content": f"教學主題：{topic}\n教學目標：{objective}\n教師剛才說：{teacher_message}",
            }
        )
        payload = json.dumps(
            {
                "model": self.model,
                "messages": messages,
                "stream": False,
                "format": "json",
                "options": {"temperature": 0.65, "num_predict": 100},
            },
            ensure_ascii=False,
        ).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}/api/chat",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = json.loads(response.read().decode("utf-8"))
            content = json.loads(body["message"]["content"])
            text = normalize_student_response(str(content.get("response", "")))
            emotion = str(content.get("emotion", "neutral"))
            text, emotion, guarded = enforce_role_consistency(
                profile,
                state,
                text[:160],
                emotion,
                teacher_message,
            )
            guard_reasons = ["role_consistency"] if guarded else []
            text, emotion, behavior_guarded = enforce_behavior_consistency(
                behavior_type,
                text,
                emotion,
            )
            if behavior_guarded:
                guard_reasons.append("behavior_consistency")
            text, length_guarded = enforce_response_length(text)
            if length_guarded:
                guard_reasons.append("response_length")
            return AgentReply(
                response=text,
                emotion=emotion,
                provider="ollama-guarded" if guard_reasons else self.name,
                behavior_type=behavior_type,
                guarded=bool(guard_reasons),
                guard_reason=",".join(guard_reasons) or None,
            )
        except (OSError, urllib.error.URLError, KeyError, ValueError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Ollama request failed: {exc}") from exc


class MockProvider(LLMProvider):
    name = "mock"

    def reply(self, profile, state, teacher_message, topic, objective) -> AgentReply:
        behavior_type = plan_student_behavior(profile, state, teacher_message)
        if profile.id == "active":
            response = "所以密度要同時看質量和體積嗎？如果體積一樣，才可以直接比較質量？"
            emotion = "curious"
        elif profile.id == "typical":
            response = "我懂公式，但還不太確定質量變大時，密度是不是一定也會變大。"
            emotion = "confused"
        elif profile.id == "misconception":
            if state.misconception_strength >= 2:
                response = "可是比較重的東西感覺就比較密，為什麼不能只看重量？"
            else:
                response = "所以還要看它占多少體積，不能只看重不重，對嗎？"
            emotion = "confused"
        elif profile.id == "reserved":
            response = "我不太確定……切小塊以後，密度真的還是一樣嗎？"
            emotion = "confused"
        elif behavior_type == "distracted":
            response = "老師，我剛剛有點沒跟上，可以再說一次問題嗎？"
            emotion = "confused"
        elif behavior_type == "off_topic":
            response = "老師，我剛剛在想午餐的布丁，前面那題沒有聽到。"
            emotion = "neutral"
        elif behavior_type == "imaginative":
            response = "如果把一顆星球壓成彈珠那麼小，它的密度會不會超大？"
            emotion = "curious"
        elif behavior_type == "redirected":
            response = "如果質量一樣，是不是體積比較小的密度比較大？"
            emotion = "confused"
        else:
            response = "老師，是不是像同樣大小的木頭和鐵，拿起來感覺不一樣？"
            emotion = "neutral"
        return AgentReply(
            response=response,
            emotion=emotion,
            provider=self.name,
            behavior_type=behavior_type,
        )


class ResilientProvider(LLMProvider):
    name = "resilient"

    def __init__(self, primary: OllamaProvider | None = None, fallback: LLMProvider | None = None):
        self.primary = primary or OllamaProvider()
        self.fallback = fallback or MockProvider()

    def reply(self, profile, state, teacher_message, topic, objective) -> AgentReply:
        if self.primary.available():
            try:
                return self.primary.reply(profile, state, teacher_message, topic, objective)
            except RuntimeError:
                pass
        return self.fallback.reply(profile, state, teacher_message, topic, objective)

