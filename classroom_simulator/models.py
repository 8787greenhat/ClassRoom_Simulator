from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class StudentProfile:
    id: str
    name: str
    personality: str
    ability_level: str
    misconception: str | None
    participation_level: str
    speaking_style: str
    color: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class StudentState:
    role_id: str
    misconception_strength: int = 0
    participation_count: int = 0
    last_spoke_turn: int = 0
    memory: list[dict[str, str]] = field(default_factory=list)
    concept_mastery: dict[str, int] = field(default_factory=dict)
    misconception_beliefs: dict[str, int] = field(default_factory=dict)
    engagement_state: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class BehaviorPlan:
    behavior_type: str
    understanding: str
    intent: str
    confidence: str
    emotion_hint: str
    misconception: str | None
    concept_mastery: dict[str, int]
    misconception_beliefs: dict[str, int]
    engagement_state: dict[str, float]
    style: tuple[str, ...]
    required_meanings: tuple[str, ...] = ()
    forbidden_meanings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        for key in ("style", "required_meanings", "forbidden_meanings"):
            data[key] = list(data[key])
        return data


@dataclass
class AgentReply:
    response: str
    emotion: str = "neutral"
    provider: str = "mock"
    model: str | None = None
    behavior_type: str = "on_task"
    guarded: bool = False
    guard_reason: str | None = None
    raw_response: str | None = None
    behavior_plan: dict[str, Any] | None = None
    generation_attempts: list[dict[str, Any]] = field(default_factory=list)
    retry_count: int = 0
    fallback_used: bool = False

