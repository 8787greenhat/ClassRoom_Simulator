import json
import re
import threading
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from classroom_simulator.evaluation import SCENARIOS, build_human_review, evaluate_provider
from classroom_simulator.evaluation_jobs import (
    EvaluationBusyError,
    EvaluationJobManager,
    EvaluationJobRequest,
    EvaluationRunNotFoundError,
    InvalidReviewError,
)
from classroom_simulator.llm import MockProvider


def mock_runner(request, progress_callback):
    return evaluate_provider(
        MockProvider(),
        scenarios=SCENARIOS[:1],
        repeats=request.repeats,
        suite_name=request.suite,
        progress_callback=progress_callback,
    )


def wait_for_terminal_status(manager, run_id, timeout=3.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        job = manager.get_job(run_id)
        if job["status"] in {"completed", "failed", "interrupted"}:
            return job
        time.sleep(0.01)
    raise AssertionError(f"job {run_id} did not finish")


class EvaluationJobLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.managers = []

    def tearDown(self):
        for manager in self.managers:
            manager.shutdown()
        self.temp_dir.cleanup()

    def make_manager(self, runner=mock_runner):
        manager = EvaluationJobManager(self.root, runner)
        self.managers.append(manager)
        return manager

    def test_job_completes_with_monotonic_progress_and_atomic_report(self):
        manager = self.make_manager()

        created = manager.create_job(
            EvaluationJobRequest(provider="mock", suite="baseline", model=None, repeats=2)
        )
        completed = wait_for_terminal_status(manager, created["run_id"])

        self.assertRegex(created["run_id"], r"^\d{8}T\d{6}Z-[0-9a-f]{8}$")
        self.assertEqual(created["status"], "queued")
        self.assertEqual(completed["status"], "completed")
        self.assertEqual(completed["progress"], {"completed": 2, "total": 2})
        run_dir = self.root / created["run_id"]
        self.assertTrue((run_dir / "job.json").is_file())
        self.assertTrue((run_dir / "report.json").is_file())
        self.assertFalse(any(run_dir.glob("*.tmp")))
        self.assertEqual(manager.get_job(created["run_id"])["report"]["total_runs"], 2)

    def test_second_job_is_rejected_while_one_is_running(self):
        started = threading.Event()
        release = threading.Event()

        def blocking_runner(request, progress_callback):
            started.set()
            release.wait(timeout=2)
            return mock_runner(request, progress_callback)

        manager = self.make_manager(blocking_runner)
        request = EvaluationJobRequest("mock", "baseline", None, 1)
        created = manager.create_job(request)
        self.assertTrue(started.wait(timeout=1))

        with self.assertRaises(EvaluationBusyError):
            manager.create_job(request)

        release.set()
        self.assertEqual(wait_for_terminal_status(manager, created["run_id"])["status"], "completed")

    def test_runner_failure_is_saved_without_traceback(self):
        def failing_runner(request, progress_callback):
            raise RuntimeError("provider unavailable")

        manager = self.make_manager(failing_runner)
        created = manager.create_job(EvaluationJobRequest("mock", "baseline", None, 1))

        failed = wait_for_terminal_status(manager, created["run_id"])

        self.assertEqual(failed["status"], "failed")
        self.assertEqual(failed["error"], "provider unavailable")
        self.assertNotIn("Traceback", json.dumps(failed))

    def test_startup_marks_unfinished_job_interrupted(self):
        run_dir = self.root / "20261122T000000Z-00000000"
        run_dir.mkdir(parents=True)
        (run_dir / "job.json").write_text(
            json.dumps(
                {
                    "run_id": run_dir.name,
                    "status": "running",
                    "created_at": "2026-11-22T00:00:00+00:00",
                    "started_at": "2026-11-22T00:00:01+00:00",
                    "finished_at": None,
                    "request": {"provider": "mock", "suite": "baseline", "model": None, "repeats": 1},
                    "progress": {"completed": 0, "total": 5},
                    "error": None,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        manager = self.make_manager()
        recovered = manager.get_job(run_dir.name)

        self.assertEqual(recovered["status"], "interrupted")
        self.assertIsNotNone(recovered["finished_at"])

    def test_history_is_newest_first_and_corruption_is_isolated(self):
        for run_id, created_at in (
            ("20261122T000000Z-00000000", "2026-11-22T00:00:00+00:00"),
            ("20261122T010000Z-11111111", "2026-11-22T01:00:00+00:00"),
        ):
            run_dir = self.root / run_id
            run_dir.mkdir(parents=True)
            (run_dir / "job.json").write_text(
                json.dumps(
                    {
                        "run_id": run_id,
                        "status": "completed",
                        "created_at": created_at,
                        "started_at": created_at,
                        "finished_at": created_at,
                        "request": {"provider": "mock", "suite": "baseline", "model": None, "repeats": 1},
                        "progress": {"completed": 1, "total": 1},
                        "error": None,
                    }
                ),
                encoding="utf-8",
            )
        corrupt_dir = self.root / "20261122T020000Z-22222222"
        corrupt_dir.mkdir()
        (corrupt_dir / "job.json").write_text("{not json", encoding="utf-8")

        manager = self.make_manager()
        history = manager.list_jobs()

        self.assertEqual(history[0]["run_id"], corrupt_dir.name)
        self.assertEqual(history[0]["status"], "corrupt")
        self.assertEqual([item["run_id"] for item in history[1:]], [
            "20261122T010000Z-11111111",
            "20261122T000000Z-00000000",
        ])

    def test_unknown_run_id_is_rejected_without_path_lookup(self):
        manager = self.make_manager()

        for run_id in ("missing", "../outside", "C:\\outside"):
            with self.subTest(run_id=run_id):
                with self.assertRaises(EvaluationRunNotFoundError):
                    manager.get_job(run_id)

    def test_shutdown_prevents_new_jobs(self):
        manager = self.make_manager()
        manager.shutdown()

        with self.assertRaises(RuntimeError):
            manager.create_job(EvaluationJobRequest("mock", "baseline", None, 1))

    def test_review_draft_persists_without_changing_hard_score(self):
        manager = self.make_manager()
        created = manager.create_job(EvaluationJobRequest("mock", "baseline", None, 1))
        completed = wait_for_terminal_status(manager, created["run_id"])
        passed_before = completed["report"]["results"][0]["passed"]

        updated = manager.update_review(
            created["run_id"],
            result_index=0,
            target="delivered",
            review={"notes": "需要再判讀"},
            complete=False,
        )

        review = updated["report"]["results"][0]["human_review"]["delivered"]
        self.assertEqual(review["status"], "pending")
        self.assertEqual(review["notes"], "需要再判讀")
        self.assertEqual(updated["report"]["results"][0]["passed"], passed_before)

        manager.shutdown()
        reloaded = self.make_manager().get_job(created["run_id"])
        self.assertEqual(
            reloaded["report"]["results"][0]["human_review"]["delivered"]["notes"],
            "需要再判讀",
        )

    def test_completed_review_requires_all_three_judgments(self):
        manager = self.make_manager()
        created = manager.create_job(EvaluationJobRequest("mock", "baseline", None, 1))
        wait_for_terminal_status(manager, created["run_id"])

        with self.assertRaises(InvalidReviewError):
            manager.update_review(
                created["run_id"],
                result_index=0,
                target="delivered",
                review={"directly_answers_teacher_request": "yes"},
                complete=True,
            )

    def test_guarded_raw_and_delivered_reviews_complete_independently(self):
        def guarded_runner(request, progress_callback):
            report = mock_runner(request, progress_callback)
            result = report["results"][0]
            result["source_category"] = "guarded"
            result["guarded"] = True
            result["raw_response"] = "模型原始回答"
            result["response"] = "系統修正回答"
            result["human_review"] = build_human_review("guarded", result["raw_response"])
            report["human_review_status"] = {
                "results": {"pending": 1, "completed": 0},
                "targets": {"pending": 2, "completed": 0},
            }
            return report

        manager = self.make_manager(guarded_runner)
        created = manager.create_job(EvaluationJobRequest("mock", "baseline", None, 1))
        wait_for_terminal_status(manager, created["run_id"])
        judgments = {
            "directly_answers_teacher_request": "yes",
            "role_consistency": "no",
            "student_realism": "uncertain",
            "notes": "人工判讀",
        }

        delivered = manager.update_review(
            created["run_id"], 0, "delivered", judgments, complete=True
        )
        self.assertEqual(delivered["report"]["human_review_status"]["targets"], {
            "pending": 1,
            "completed": 1,
        })
        self.assertEqual(delivered["report"]["human_review_status"]["results"], {
            "pending": 1,
            "completed": 0,
        })

        both = manager.update_review(
            created["run_id"], 0, "raw_model", judgments, complete=True
        )
        self.assertEqual(both["report"]["human_review_status"]["targets"], {
            "pending": 0,
            "completed": 2,
        })
        self.assertEqual(both["report"]["human_review_status"]["results"], {
            "pending": 0,
            "completed": 1,
        })

    def test_unavailable_review_target_and_unknown_fields_are_rejected(self):
        manager = self.make_manager()
        created = manager.create_job(EvaluationJobRequest("mock", "baseline", None, 1))
        wait_for_terminal_status(manager, created["run_id"])

        with self.assertRaises(InvalidReviewError):
            manager.update_review(created["run_id"], 0, "raw_model", {}, complete=False)
        with self.assertRaises(InvalidReviewError):
            manager.update_review(
                created["run_id"],
                0,
                "delivered",
                {"score": 5},
                complete=False,
            )


if __name__ == "__main__":
    unittest.main()
