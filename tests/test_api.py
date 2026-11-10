import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

from classroom_simulator import main
from classroom_simulator.db import Database
from classroom_simulator.llm import MockProvider
from classroom_simulator.service import ClassroomService


class ModelSelectionApiTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_service = main.service
        main.service = ClassroomService(
            Database(Path(self.temp_dir.name) / "api-test.db"),
            MockProvider(),
        )

    def tearDown(self):
        main.service = self.original_service
        self.temp_dir.cleanup()

    def test_models_endpoint_lists_installed_models(self):
        installed = [
            {
                "name": "qwen2.5:7b",
                "size": 4683087332,
                "parameter_size": "7.6B",
                "quantization_level": "Q4_K_M",
            }
        ]
        with patch.object(main.ollama, "installed_models", return_value=installed):
            payload = main.models()

        self.assertTrue(payload["ollama_available"])
        self.assertEqual(payload["models"], installed)

    def test_message_rejects_a_model_that_is_not_installed(self):
        session = main.create_session(main.CreateSessionRequest())
        request = main.TeacherMessageRequest(message="小明，你哪裡不確定？", model="missing:7b")

        with patch.object(main.ollama, "installed_models", return_value=[]):
            with self.assertRaises(HTTPException) as raised:
                main.send_message(session["session"]["id"], request)

        self.assertEqual(raised.exception.status_code, 422)

    def test_message_accepts_an_installed_model_without_breaking_old_api(self):
        session = main.create_session(main.CreateSessionRequest())
        selected = main.TeacherMessageRequest(
            message="小明，你哪裡不確定？",
            model="qwen2.5:7b",
        )
        legacy = main.TeacherMessageRequest(message="小安，你想到什麼問題？")

        with patch.object(
            main.ollama,
            "installed_models",
            return_value=[{"name": "qwen2.5:7b"}],
        ), patch.object(main, "ResilientProvider", return_value=MockProvider()):
            selected_snapshot = main.send_message(session["session"]["id"], selected)
        legacy_snapshot = main.send_message(session["session"]["id"], legacy)

        self.assertEqual(len(selected_snapshot["events"]), 2)
        self.assertEqual(len(legacy_snapshot["events"]), 4)


if __name__ == "__main__":
    unittest.main()
