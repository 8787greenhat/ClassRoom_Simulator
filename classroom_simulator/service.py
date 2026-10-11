from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from .db import Database
from .llm import LLMProvider, ResilientProvider
from .models import StudentProfile, StudentState
from .roles import PROFILES_BY_ID, STUDENT_PROFILES


class SessionNotFoundError(LookupError):
    pass


class SessionClosedError(RuntimeError):
    pass


class ClassroomService:
    def __init__(self, database: Database, provider: LLMProvider | None = None):
        self.database = database
        self.provider = provider or ResilientProvider()

    @staticmethod
    def now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def create_session(
        self,
        topic: str = "國中自然科：密度",
        objective: str = "理解密度是質量與體積的比值，並修正常見迷思",
    ) -> dict:
        session_id = uuid4().hex
        self.database.create_session(session_id, topic.strip(), objective.strip(), self.now())
        return self.snapshot(session_id)

    def _require_session(self, session_id: str) -> dict:
        session = self.database.get_session(session_id)
        if not session:
            raise SessionNotFoundError(session_id)
        return session

    def _choose_student(
        self,
        message: str,
        states: dict[str, StudentState],
        turn: int,
    ) -> StudentProfile:
        for profile in STUDENT_PROFILES:
            if profile.name in message:
                return profile

        normalized = message.lower()
        if any(keyword in normalized for keyword in ("錯", "迷思", "越重", "為什麼不能")):
            return PROFILES_BY_ID["misconception"]
        if any(keyword in normalized for keyword in ("有人不懂", "沒回答", "點名")):
            return PROFILES_BY_ID["reserved"]

        rotation = ("active", "typical", "misconception", "reserved", "distracted")
        ranked = sorted(
            rotation,
            key=lambda role_id: (
                states[role_id].participation_count,
                states[role_id].last_spoke_turn,
                rotation.index(role_id),
            ),
        )
        if "？" in message or "?" in message:
            return PROFILES_BY_ID[ranked[0]]
        return PROFILES_BY_ID["active" if turn == 1 else ranked[0]]

    @staticmethod
    def _update_misconception(state: StudentState, profile: StudentProfile, message: str) -> None:
        if state.misconception_strength <= 0 or not profile.misconception:
            return
        evidence_terms = ("質量", "體積", "密度", "除以", "比值")
        check_terms = ("所以", "再說一次", "試著", "舉例", "為什麼", "對不對")
        evidence_score = sum(term in message for term in evidence_terms)
        has_check = any(term in message for term in check_terms)
        if evidence_score >= 2 and has_check:
            state.misconception_strength = max(0, state.misconception_strength - 1)

    def send_teacher_message(self, session_id: str, message: str) -> dict:
        session = self._require_session(session_id)
        if session["status"] != "active":
            raise SessionClosedError(session_id)
        message = message.strip()
        if not message:
            raise ValueError("教師發言不可為空白")

        turn = self.database.next_turn_number(session_id)
        states = self.database.get_states(session_id)
        profile = self._choose_student(message, states, turn)
        state = states[profile.id]

        self.database.add_event(
            session_id, turn, "teacher", None, message, {}, self.now()
        )
        self._update_misconception(state, profile, message)
        reply = self.provider.reply(
            profile, state, message, session["topic"], session["objective"]
        )

        state.participation_count += 1
        state.last_spoke_turn = turn
        state.memory.extend(
            [
                {"role": "user", "content": message},
                {"role": "assistant", "content": reply.response},
            ]
        )
        self.database.save_state(session_id, state)
        self.database.add_event(
            session_id,
            turn,
            "student",
            profile.id,
            reply.response,
            {
                "emotion": reply.emotion,
                "provider": reply.provider,
                "misconception_strength": state.misconception_strength,
            },
            self.now(),
        )
        return self.snapshot(session_id)

    def finish_session(self, session_id: str) -> dict:
        self._require_session(session_id)
        self.database.set_session_status(session_id, "finished")
        return self.snapshot(session_id)

    def snapshot(self, session_id: str) -> dict:
        session = self._require_session(session_id)
        states = self.database.get_states(session_id)
        return {
            "session": session,
            "students": [
                {**profile.to_dict(), "state": states[profile.id].to_dict()}
                for profile in STUDENT_PROFILES
            ],
            "events": self.database.list_events(session_id),
        }

