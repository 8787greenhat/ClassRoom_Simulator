from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from .learning import ensure_concept_state, initial_concept_state
from .models import StudentState
from .roles import PROFILES_BY_ID, STUDENT_PROFILES, initial_misconception_strength


SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    topic TEXT NOT NULL,
    objective TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS student_states (
    session_id TEXT NOT NULL,
    role_id TEXT NOT NULL,
    misconception_strength INTEGER NOT NULL,
    participation_count INTEGER NOT NULL DEFAULT 0,
    last_spoke_turn INTEGER NOT NULL DEFAULT 0,
    memory_json TEXT NOT NULL DEFAULT '[]',
    concept_state_json TEXT NOT NULL DEFAULT '{}',
    PRIMARY KEY (session_id, role_id),
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    turn_number INTEGER NOT NULL,
    speaker_type TEXT NOT NULL,
    speaker_id TEXT,
    content TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);
CREATE INDEX IF NOT EXISTS idx_events_session ON events(session_id, id);
"""


class Database:
    def __init__(self, path: str | Path):
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.executescript(SCHEMA)
            columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(student_states)").fetchall()
            }
            if "concept_state_json" not in columns:
                connection.execute(
                    "ALTER TABLE student_states ADD COLUMN concept_state_json TEXT NOT NULL DEFAULT '{}'"
                )

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def create_session(self, session_id: str, topic: str, objective: str, created_at: str) -> None:
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO sessions(id, topic, objective, created_at) VALUES (?, ?, ?, ?)",
                (session_id, topic, objective, created_at),
            )
            connection.executemany(
                """
                INSERT INTO student_states(
                    session_id, role_id, misconception_strength, participation_count,
                    last_spoke_turn, memory_json, concept_state_json
                ) VALUES (?, ?, ?, 0, 0, '[]', ?)
                """,
                [
                    (
                        session_id,
                        profile.id,
                        initial_misconception_strength(profile),
                        json.dumps(
                            dict(
                                zip(
                                    ("mastery", "beliefs"),
                                    initial_concept_state(profile),
                                )
                            ),
                            ensure_ascii=False,
                        ),
                    )
                    for profile in STUDENT_PROFILES
                ],
            )

    def get_session(self, session_id: str) -> dict | None:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
        return dict(row) if row else None

    def set_session_status(self, session_id: str, status: str) -> None:
        with self.connect() as connection:
            connection.execute("UPDATE sessions SET status = ? WHERE id = ?", (status, session_id))

    def next_turn_number(self, session_id: str) -> int:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT COALESCE(MAX(turn_number), 0) + 1 AS next_turn FROM events WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        return int(row["next_turn"])

    def add_event(
        self,
        session_id: str,
        turn_number: int,
        speaker_type: str,
        speaker_id: str | None,
        content: str,
        metadata: dict,
        created_at: str,
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO events(
                    session_id, turn_number, speaker_type, speaker_id,
                    content, metadata_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    turn_number,
                    speaker_type,
                    speaker_id,
                    content,
                    json.dumps(metadata, ensure_ascii=False),
                    created_at,
                ),
            )

    def list_events(self, session_id: str) -> list[dict]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM events WHERE session_id = ? ORDER BY id", (session_id,)
            ).fetchall()
        events = []
        for row in rows:
            item = dict(row)
            item["metadata"] = json.loads(item.pop("metadata_json"))
            events.append(item)
        return events

    def get_states(self, session_id: str) -> dict[str, StudentState]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM student_states WHERE session_id = ?", (session_id,)
            ).fetchall()
        states = {}
        for row in rows:
            try:
                concept_state = json.loads(row["concept_state_json"] or "{}")
            except (TypeError, json.JSONDecodeError):
                concept_state = {}
            if not isinstance(concept_state, dict):
                concept_state = {}
            mastery = concept_state.get("mastery", {})
            beliefs = concept_state.get("beliefs", {})
            if not isinstance(mastery, dict):
                mastery = {}
            if not isinstance(beliefs, dict):
                beliefs = {}
            state = StudentState(
                role_id=row["role_id"],
                misconception_strength=row["misconception_strength"],
                participation_count=row["participation_count"],
                last_spoke_turn=row["last_spoke_turn"],
                memory=json.loads(row["memory_json"]),
                concept_mastery=mastery,
                misconception_beliefs=beliefs,
            )
            ensure_concept_state(PROFILES_BY_ID[row["role_id"]], state)
            states[row["role_id"]] = state
        return states

    def save_state(self, session_id: str, state: StudentState) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE student_states
                SET misconception_strength = ?, participation_count = ?,
                    last_spoke_turn = ?, memory_json = ?, concept_state_json = ?
                WHERE session_id = ? AND role_id = ?
                """,
                (
                    state.misconception_strength,
                    state.participation_count,
                    state.last_spoke_turn,
                    json.dumps(state.memory[-8:], ensure_ascii=False),
                    json.dumps(
                        {
                            "mastery": state.concept_mastery,
                            "beliefs": state.misconception_beliefs,
                        },
                        ensure_ascii=False,
                    ),
                    session_id,
                    state.role_id,
                ),
            )

