import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

from classroom_simulator import main
from classroom_simulator.db import Database
from classroom_simulator.evaluation import SCENARIOS, evaluate_provider
from classroom_simulator.evaluation_archive import LegacyEvaluationArchive
from classroom_simulator.evaluation_jobs import EvaluationJobManager
from classroom_simulator.llm import MockProvider
from classroom_simulator.service import ClassroomService


class EvaluationApiTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.original_manager = getattr(main, "evaluation_manager", None)
        self.original_archive = getattr(main, "evaluation_archive", None)
        self.original_service = main.service
        main.evaluation_manager = EvaluationJobManager(root / "runs", self._runner)
        main.evaluation_archive = LegacyEvaluationArchive(
            main.PROJECT_DIR,
            root / "legacy-reviews",
        )
        main.service = ClassroomService(Database(root / "api-test.db"), MockProvider())

    def tearDown(self):
        main.evaluation_manager.shutdown()
        if self.original_manager is None:
            delattr(main, "evaluation_manager")
        else:
            main.evaluation_manager = self.original_manager
        if self.original_archive is None:
            delattr(main, "evaluation_archive")
        else:
            main.evaluation_archive = self.original_archive
        main.service = self.original_service
        self.temp_dir.cleanup()

    @staticmethod
    def _runner(request, progress):
        return evaluate_provider(
            MockProvider(),
            scenarios=SCENARIOS[:1],
            repeats=request.repeats,
            suite_name=request.suite,
            progress_callback=progress,
        )

    @staticmethod
    def _route_status(path, method):
        route = next(
            route
            for route in main.app.routes
            if getattr(route, "path", None) == path and method in getattr(route, "methods", set())
        )
        return route.status_code

    def _wait_for_completion(self, run_id):
        for _ in range(100):
            detail = main.get_evaluation(run_id)
            if detail["status"] not in {"queued", "running"}:
                return detail
            time.sleep(0.01)
        self.fail("evaluation did not complete")

    def test_mock_run_history_detail_and_existing_apis_remain_usable(self):
        page = main.evaluation_page()
        self.assertEqual(Path(page.path).name, "evaluation.html")
        self.assertTrue(Path(page.path).is_file())
        self.assertEqual(self._route_status("/api/evaluations", "POST"), 202)

        created = main.create_evaluation(
            main.EvaluationCreateRequest(provider="mock", suite="baseline", repeats=1)
        )
        completed = self._wait_for_completion(created["run_id"])
        self.assertEqual(completed["status"], "completed")
        self.assertEqual(completed["report"]["report_schema_version"], "2.0")

        history = main.list_evaluations()["evaluations"]
        self.assertEqual(len(history), 5)
        self.assertEqual(history[0]["run_id"], created["run_id"])
        self.assertTrue(all("results" not in item for item in history))
        self.assertEqual(sum(bool(item.get("legacy")) for item in history), 4)

        legacy_id = next(item["run_id"] for item in history if item.get("legacy"))
        legacy_detail = main.get_evaluation(legacy_id)
        self.assertEqual(legacy_detail["status"], "completed")
        self.assertTrue(legacy_detail["legacy"])
        self.assertTrue(legacy_detail["report"]["results"])

        self.assertTrue(main.health()["ok"])
        session = main.create_session(main.CreateSessionRequest())
        snapshot = main.send_message(
            session["session"]["id"],
            main.TeacherMessageRequest(message="小明，你怎麼想？"),
        )
        self.assertTrue(snapshot["events"])

    def test_create_validation_and_busy_status(self):
        invalid_payloads = (
            {"provider": "other", "suite": "baseline", "repeats": 1},
            {"provider": "mock", "suite": "unknown", "repeats": 1},
            {"provider": "mock", "suite": "baseline", "repeats": 0},
        )
        for payload in invalid_payloads:
            with self.subTest(payload=payload), self.assertRaises(Exception):
                main.EvaluationCreateRequest(**payload)

        with self.assertRaises(HTTPException) as mock_model:
            main.create_evaluation(
                main.EvaluationCreateRequest(
                    provider="mock",
                    suite="baseline",
                    model="qwen2.5:3b",
                    repeats=1,
                )
            )
        self.assertEqual(mock_model.exception.status_code, 422)

        with self.assertRaises(HTTPException) as missing_model:
            main.create_evaluation(
                main.EvaluationCreateRequest(provider="ollama", suite="baseline", repeats=1)
            )
        self.assertEqual(missing_model.exception.status_code, 422)

        request = main.EvaluationCreateRequest(
            provider="ollama",
            suite="baseline",
            model="missing:7b",
            repeats=1,
        )
        with patch.object(main.ollama, "installed_models", return_value=[]):
            with self.assertRaises(HTTPException) as uninstalled:
                main.create_evaluation(request)
        self.assertEqual(uninstalled.exception.status_code, 422)

        with patch.object(main.ollama, "installed_models", side_effect=RuntimeError("offline")):
            with self.assertRaises(HTTPException) as unavailable:
                main.create_evaluation(request)
        self.assertEqual(unavailable.exception.status_code, 422)

        with patch.object(
            main.ollama,
            "installed_models",
            return_value=[{"name": "qwen2.5:3b"}],
        ):
            accepted = main.create_evaluation(
                main.EvaluationCreateRequest(
                    provider="ollama",
                    suite="baseline",
                    model="qwen2.5:3b",
                    repeats=1,
                )
            )
        self.assertEqual(self._wait_for_completion(accepted["run_id"])["status"], "completed")

    def test_second_active_job_returns_conflict(self):
        started = threading.Event()
        release = threading.Event()

        def blocking_runner(request, progress):
            started.set()
            release.wait(timeout=2)
            return self._runner(request, progress)

        main.evaluation_manager.shutdown()
        root = Path(self.temp_dir.name) / "blocking-runs"
        main.evaluation_manager = EvaluationJobManager(root, blocking_runner)
        first = main.create_evaluation(
            main.EvaluationCreateRequest(provider="mock", suite="baseline", repeats=1)
        )
        self.assertTrue(started.wait(timeout=1))
        try:
            with self.assertRaises(HTTPException) as busy:
                main.create_evaluation(
                    main.EvaluationCreateRequest(provider="mock", suite="baseline", repeats=1)
                )
            self.assertEqual(busy.exception.status_code, 409)
        finally:
            release.set()
        self.assertEqual(self._wait_for_completion(first["run_id"])["status"], "completed")

    def test_review_supports_draft_complete_and_target_validation(self):
        created = main.create_evaluation(
            main.EvaluationCreateRequest(provider="mock", suite="baseline", repeats=1)
        )
        self._wait_for_completion(created["run_id"])

        draft = main.review_evaluation_result(
            created["run_id"],
            0,
            main.EvaluationReviewRequest(
                target="delivered",
                role_consistency="yes",
                notes="待確認是否直接回答",
            ),
        )
        delivered = draft["report"]["results"][0]["human_review"]["delivered"]
        self.assertEqual(delivered["status"], "pending")
        self.assertEqual(delivered["role_consistency"], "yes")

        with self.assertRaises(HTTPException) as incomplete:
            main.review_evaluation_result(
                created["run_id"],
                0,
                main.EvaluationReviewRequest(target="delivered", complete=True),
            )
        self.assertEqual(incomplete.exception.status_code, 422)

        completed = main.review_evaluation_result(
            created["run_id"],
            0,
            main.EvaluationReviewRequest(
                target="delivered",
                directly_answers_teacher_request="yes",
                role_consistency="yes",
                student_realism="uncertain",
                notes="完成覆核",
                complete=True,
            ),
        )
        review = completed["report"]["results"][0]["human_review"]["delivered"]
        self.assertEqual(review["status"], "completed")
        self.assertIsNotNone(review["reviewed_at"])

        with self.assertRaises(HTTPException) as unavailable:
            main.review_evaluation_result(
                created["run_id"],
                0,
                main.EvaluationReviewRequest(target="raw_model"),
            )
        self.assertEqual(unavailable.exception.status_code, 422)

    def test_missing_and_corrupt_details_are_explained_without_paths(self):
        with self.assertRaises(HTTPException) as missing:
            main.get_evaluation("../../secret")
        self.assertEqual(missing.exception.status_code, 404)

        run_dir = Path(main.evaluation_manager.root) / "20261123T120000Z-deadbeef"
        run_dir.mkdir(parents=True)
        (run_dir / "job.json").write_text("{broken", encoding="utf-8")
        with self.assertRaises(HTTPException) as corrupt:
            main.get_evaluation(run_dir.name)
        self.assertEqual(corrupt.exception.status_code, 500)
        self.assertNotIn(str(run_dir), str(corrupt.exception.detail))

    def test_runtime_error_is_recorded_as_result_evidence(self):
        class FailingProvider(MockProvider):
            name = "ollama"

            def reply(self, *args, **kwargs):
                raise RuntimeError("synthetic provider failure")

        main.evaluation_manager.shutdown()
        root = Path(self.temp_dir.name) / "failing-runs"

        def failing_runner(request, progress):
            return evaluate_provider(
                FailingProvider(),
                scenarios=SCENARIOS[:1],
                repeats=1,
                suite_name=request.suite,
                progress_callback=progress,
            )

        main.evaluation_manager = EvaluationJobManager(root, failing_runner)
        created = main.create_evaluation(
            main.EvaluationCreateRequest(provider="mock", suite="baseline", repeats=1)
        )
        completed = self._wait_for_completion(created["run_id"])
        result = completed["report"]["results"][0]
        self.assertEqual(result["source_category"], "error")
        self.assertIn("synthetic provider failure", result["error"])
        self.assertEqual(result["human_review"], {})


if __name__ == "__main__":
    unittest.main()
