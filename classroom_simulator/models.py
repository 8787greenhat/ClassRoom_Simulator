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

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AgentReply:
    response: str
    emotion: str = "neutral"
    provider: str = "mock"

