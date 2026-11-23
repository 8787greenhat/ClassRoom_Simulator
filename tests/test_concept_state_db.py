import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from classroom_simulator.db import Database


class ConceptStatePersistenceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.path = Path(self.temp_dir.name) / "state.db"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_new_session_persists_and_round_trips_concept_state(self):
        database = Database(self.path)
        database.create_session("session", "密度", "理解密度", "2026-11-23T00:00:00+00:00")

        state = database.get_states("session")["misconception"]
        self.assertEqual(state.concept_mastery["density_ratio"], 0)
        self.assertEqual(state.misconception_beliefs["heavier_means_denser"], 3)

        state.concept_mastery["density_ratio"] = 1
        state.misconception_beliefs["heavier_means_denser"] = 2
        state.misconception_strength = 2
        database.save_state("session", state)

        restored = database.get_states("session")["misconception"]
        self.assertEqual(restored.concept_mastery["density_ratio"], 1)
        self.assertEqual(restored.misconception_beliefs["heavier_means_denser"], 2)
        self.assertEqual(restored.misconception_strength, 2)

    def test_legacy_student_state_table_is_migrated_without_losing_scalar_state(self):
        connection = sqlite3.connect(self.path)
        try:
            connection.execute(
                """
                CREATE TABLE student_states (
                    session_id TEXT NOT NULL,
                    role_id TEXT NOT NULL,
                    misconception_strength INTEGER NOT NULL,
                    participation_count INTEGER NOT NULL DEFAULT 0,
                    last_spoke_turn INTEGER NOT NULL DEFAULT 0,
                    memory_json TEXT NOT NULL DEFAULT '[]',
                    PRIMARY KEY (session_id, role_id)
                )
                """
            )
            connection.execute(
                "INSERT INTO student_states VALUES (?, ?, ?, ?, ?, ?)",
                ("legacy", "misconception", 2, 4, 7, json.dumps([])),
            )
            connection.commit()
        finally:
            connection.close()

        database = Database(self.path)
        state = database.get_states("legacy")["misconception"]

        self.assertEqual(state.misconception_strength, 2)
        self.assertEqual(state.misconception_beliefs["heavier_means_denser"], 2)
        self.assertEqual(state.participation_count, 4)
        connection = sqlite3.connect(self.path)
        try:
            columns = {row[1] for row in connection.execute("PRAGMA table_info(student_states)")}
        finally:
            connection.close()
        self.assertIn("concept_state_json", columns)


if __name__ == "__main__":
    unittest.main()
