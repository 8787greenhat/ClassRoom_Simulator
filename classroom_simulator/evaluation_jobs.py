from __future__ import annotations

import json
import re
import threading
import time
from concurrent.futures import Executor, ThreadPoolExecutor
from copy import deepcopy
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
from uuid import uuid4


RUN_ID_PATTERN = re.compile(r"^\d{8}T\d{6}Z-[0-9a-f]{8}$")


class EvaluationBusyError(RuntimeError):
    pass


class EvaluationRunNotFoundError(LookupError):
    pass


class EvaluationResultNotFoundError(LookupError):
    pass


class InvalidReviewError(ValueError):
    pass


@dataclass(frozen=True)
class EvaluationJobRequest:
    provider: str
    suite: str
    model: str | None
    repeats: int


ProgressCallback = Callable[[int, int], None]
EvaluationRunner = Callable[[EvaluationJobRequest, ProgressCallback], dict]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _atomic_write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    for attempt in range(5):
        try:
            temporary.replace(path)
            return
        except PermissionError:
            if attempt == 4:
                raise
            time.sleep(0.01 * (attempt + 1))


class EvaluationJobManager:
    def __init__(
        self,
        root: Path,
        runner: EvaluationRunner,
        executor: Executor | None = None,
    ):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.runner = runner
        self.executor = executor or ThreadPoolExecutor(max_workers=1, thread_name_prefix="evaluation")
        self._lock = threading.RLock()
        self._active_run_id: str | None = None
        self._closed = False
        self._recover_unfinished_jobs()

    def create_job(self, request: EvaluationJobRequest) -> dict:
        with self._lock:
            if self._closed:
                raise RuntimeError("evaluation job manager is shut down")
            if self._active_run_id is not None:
                raise EvaluationBusyError(self._active_run_id)

            timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            run_id = f"{timestamp}-{uuid4().hex[:8]}"
            job = {
                "run_id": run_id,
                "status": "queued",
                "created_at": _now(),
                "started_at": None,
                "finished_at": None,
                "request": asdict(request),
                "progress": {"completed": 0, "total": 0},
                "error": None,
            }
            self._write_job(job)
            self._active_run_id = run_id
            self.executor.submit(self._run_job, run_id, request)
            return deepcopy(job)

    def list_jobs(self) -> list[dict]:
        jobs = []
        for run_dir in self.root.iterdir():
            if not run_dir.is_dir() or not RUN_ID_PATTERN.fullmatch(run_dir.name):
                continue
            try:
                job = self.get_job(run_dir.name)
                job.pop("report", None)
                jobs.append(job)
            except (OSError, ValueError, json.JSONDecodeError):
                jobs.append(
                    {
                        "run_id": run_dir.name,
                        "status": "corrupt",
                        "created_at": None,
                        "error": "job data is unreadable",
                    }
                )
        return sorted(jobs, key=lambda item: item["run_id"], reverse=True)

    def get_job(self, run_id: str) -> dict:
        if not RUN_ID_PATTERN.fullmatch(run_id):
            raise EvaluationRunNotFoundError(run_id)
        try:
            job = self._read_job(run_id)
        except FileNotFoundError as exc:
            raise EvaluationRunNotFoundError(run_id) from exc
        report_path = self.root / run_id / "report.json"
        if report_path.is_file():
            try:
                job["report"] = self._read_report(run_id)
            except (OSError, ValueError, json.JSONDecodeError):
                if job.get("status") == "completed":
                    job["status"] = "corrupt"
                    job["error"] = "completed report is unreadable"
                else:
                    raise
        elif job.get("status") == "completed":
            job["status"] = "corrupt"
            job["error"] = "completed report is missing"
        return job

    def update_review(
        self,
        run_id: str,
        result_index: int,
        target: str,
        review: dict,
        complete: bool,
    ) -> dict:
        allowed_fields = {
            "directly_answers_teacher_request",
            "role_consistency",
            "student_realism",
            "notes",
        }
        unknown_fields = set(review) - allowed_fields
        if unknown_fields:
            raise InvalidReviewError(f"unsupported review fields: {sorted(unknown_fields)}")

        with self._lock:
            job = self.get_job(run_id)
            if job.get("status") != "completed" or "report" not in job:
                raise InvalidReviewError("reviews require a completed report")
            results = job["report"].get("results", [])
            if not isinstance(result_index, int) or not 0 <= result_index < len(results):
                raise EvaluationResultNotFoundError(result_index)
            targets = results[result_index].get("human_review", {})
            if target not in targets:
                raise InvalidReviewError(f"review target is unavailable: {target}")

            current = targets[target]
            for field in (
                "directly_answers_teacher_request",
                "role_consistency",
                "student_realism",
            ):
                if field not in review:
                    continue
                value = review[field]
                if value is not None and value not in {"yes", "no", "uncertain"}:
                    raise InvalidReviewError(f"invalid judgment for {field}")
                current[field] = value
            if "notes" in review:
                if not isinstance(review["notes"], str):
                    raise InvalidReviewError("review notes must be text")
                current["notes"] = review["notes"]

            required = (
                "directly_answers_teacher_request",
                "role_consistency",
                "student_realism",
            )
            if complete and any(current.get(field) not in {"yes", "no", "uncertain"} for field in required):
                raise InvalidReviewError("all judgments are required to complete a review")
            current["status"] = "completed" if complete else "pending"
            current["reviewed_at"] = _now() if complete else None
            job["report"]["human_review_status"] = self._review_status(results)
            _atomic_write_json(self.root / run_id / "report.json", job["report"])
            return self.get_job(run_id)

    def shutdown(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
        self.executor.shutdown(wait=True)

    def _run_job(self, run_id: str, request: EvaluationJobRequest) -> None:
        try:
            with self._lock:
                job = self._read_job(run_id)
                job["status"] = "running"
                job["started_at"] = _now()
                self._write_job(job)

            def update_progress(completed: int, total: int) -> None:
                with self._lock:
                    current = self._read_job(run_id)
                    current["progress"] = {"completed": completed, "total": total}
                    self._write_job(current)

            report = self.runner(request, update_progress)
            with self._lock:
                _atomic_write_json(self.root / run_id / "report.json", report)
                job = self._read_job(run_id)
                job["status"] = "completed"
                job["finished_at"] = _now()
                if job["progress"]["total"] == 0:
                    total = int(report.get("total_runs", 0))
                    job["progress"] = {"completed": total, "total": total}
                self._write_job(job)
        except Exception as exc:
            with self._lock:
                try:
                    job = self._read_job(run_id)
                except (OSError, ValueError, json.JSONDecodeError):
                    job = {
                        "run_id": run_id,
                        "request": asdict(request),
                        "progress": {"completed": 0, "total": 0},
                        "created_at": _now(),
                        "started_at": None,
                    }
                job["status"] = "failed"
                job["finished_at"] = _now()
                job["error"] = str(exc)
                self._write_job(job)
        finally:
            with self._lock:
                if self._active_run_id == run_id:
                    self._active_run_id = None

    def _read_job(self, run_id: str) -> dict:
        path = self.root / run_id / "job.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError("job data must be a JSON object")
        if value.get("run_id") != run_id:
            raise ValueError("job run id does not match its directory")
        if value.get("status") not in {
            "queued",
            "running",
            "completed",
            "failed",
            "interrupted",
        }:
            raise ValueError("job status is invalid")
        return value

    def _read_report(self, run_id: str) -> dict:
        path = self.root / run_id / "report.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError("evaluation report must be a JSON object")
        if not isinstance(value.get("results"), list):
            raise ValueError("evaluation report results must be a list")
        return value

    def _write_job(self, job: dict) -> None:
        _atomic_write_json(self.root / job["run_id"] / "job.json", job)

    def _recover_unfinished_jobs(self) -> None:
        for run_dir in self.root.iterdir():
            if not run_dir.is_dir() or not RUN_ID_PATTERN.fullmatch(run_dir.name):
                continue
            try:
                job = self._read_job(run_dir.name)
            except (OSError, ValueError, json.JSONDecodeError):
                continue
            if job.get("status") not in {"queued", "running"}:
                continue
            job["status"] = "interrupted"
            job["finished_at"] = _now()
            job["error"] = "server restarted before evaluation completed"
            self._write_job(job)

    @staticmethod
    def _review_status(results: list[dict]) -> dict:
        reviewable_results = [result for result in results if result.get("human_review")]
        targets = [
            review
            for result in reviewable_results
            for review in result["human_review"].values()
        ]
        completed_targets = sum(review.get("status") == "completed" for review in targets)
        completed_results = sum(
            all(review.get("status") == "completed" for review in result["human_review"].values())
            for result in reviewable_results
        )
        return {
            "results": {
                "pending": len(reviewable_results) - completed_results,
                "completed": completed_results,
            },
            "targets": {
                "pending": len(targets) - completed_targets,
                "completed": completed_targets,
            },
        }
