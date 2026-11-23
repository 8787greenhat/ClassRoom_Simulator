from __future__ import annotations

import os
import json
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from .db import Database
from .evaluation import SCENARIO_SUITES, evaluate_provider
from .evaluation_archive import (
    LegacyArchiveError,
    LegacyEvaluationArchive,
    LegacyReportNotFoundError,
)
from .evaluation_jobs import (
    EvaluationBusyError,
    EvaluationJobManager,
    EvaluationJobRequest,
    EvaluationResultNotFoundError,
    EvaluationRunNotFoundError,
    InvalidReviewError,
)
from .llm import MockProvider, OllamaProvider, ResilientProvider
from .roles import STUDENT_PROFILES
from .service import ClassroomService, SessionClosedError, SessionNotFoundError


BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
STATIC_DIR = BASE_DIR / "static"
DB_PATH = Path(os.getenv("CLASSROOM_DB_PATH", PROJECT_DIR / "data" / "classroom.db"))
EVALUATION_DATA_DIR = Path(
    os.getenv("EVALUATION_DATA_DIR", PROJECT_DIR / "data" / "evaluations")
)

ollama = OllamaProvider()
service = ClassroomService(Database(DB_PATH), ResilientProvider(primary=ollama))


def run_evaluation_job(request: EvaluationJobRequest, progress) -> dict:
    if request.provider == "mock":
        provider = MockProvider()
    else:
        provider = OllamaProvider(
            base_url=ollama.base_url,
            model=request.model,
            timeout=ollama.timeout,
        )
    return evaluate_provider(
        provider,
        scenarios=SCENARIO_SUITES[request.suite],
        repeats=request.repeats,
        suite_name=request.suite,
        progress_callback=progress,
    )


evaluation_manager = EvaluationJobManager(EVALUATION_DATA_DIR, run_evaluation_job)
evaluation_archive = LegacyEvaluationArchive(
    PROJECT_DIR,
    EVALUATION_DATA_DIR / "legacy-reviews",
)

app = FastAPI(title="ClassRoom Simulator", version="0.1.0")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class CreateSessionRequest(BaseModel):
    topic: str = Field(default="國中自然科：密度", min_length=1, max_length=100)
    objective: str = Field(
        default="理解密度是質量與體積的比值，並修正常見迷思",
        min_length=1,
        max_length=200,
    )


class TeacherMessageRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    model: str | None = Field(default=None, min_length=1, max_length=100)


class EvaluationCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: Literal["mock", "ollama"]
    suite: Literal["baseline", "holdout"] = "baseline"
    model: str | None = Field(default=None, min_length=1, max_length=100)
    repeats: int = Field(default=1, ge=1, le=100)


class EvaluationReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target: Literal["delivered", "raw_model"]
    directly_answers_teacher_request: Literal["yes", "no", "uncertain"] | None = None
    role_consistency: Literal["yes", "no", "uncertain"] | None = None
    student_realism: Literal["yes", "no", "uncertain"] | None = None
    notes: str | None = Field(default=None, max_length=2000)
    complete: bool = False


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/evaluations", include_in_schema=False)
def evaluation_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "evaluation.html")


@app.get("/api/health")
def health() -> dict:
    return {
        "ok": True,
        "ollama_available": ollama.available(),
        "model": ollama.model,
        "fallback": "mock",
    }


@app.get("/api/models")
def models() -> dict:
    try:
        installed = ollama.installed_models()
    except RuntimeError:
        installed = []
    return {
        "ollama_available": bool(installed),
        "default": ollama.model,
        "models": installed,
    }


def _legacy_detail(report: dict) -> dict:
    return {
        "run_id": report["run_id"],
        "status": "completed",
        "legacy": True,
        "created_at": report.get("generated_at"),
        "started_at": None,
        "finished_at": report.get("generated_at"),
        "request": None,
        "progress": {
            "completed": len(report.get("results", [])),
            "total": len(report.get("results", [])),
        },
        "error": None,
        "report": report,
    }


@app.post("/api/evaluations", status_code=202)
def create_evaluation(payload: EvaluationCreateRequest) -> dict:
    if payload.provider == "mock" and payload.model is not None:
        raise HTTPException(status_code=422, detail="Mock 評測不接受模型名稱")
    if payload.provider == "ollama":
        if payload.model is None:
            raise HTTPException(status_code=422, detail="Ollama 評測必須指定模型")
        try:
            installed_names = {item["name"] for item in ollama.installed_models()}
        except RuntimeError as exc:
            raise HTTPException(status_code=422, detail="Ollama 無法取得模型清單") from exc
        if payload.model not in installed_names:
            raise HTTPException(
                status_code=422,
                detail=f"模型未安裝或不可用：{payload.model}",
            )
    request = EvaluationJobRequest(
        provider=payload.provider,
        suite=payload.suite,
        model=payload.model,
        repeats=payload.repeats,
    )
    try:
        job = evaluation_manager.create_job(request)
    except EvaluationBusyError as exc:
        raise HTTPException(status_code=409, detail="已有評測正在執行") from exc
    job["legacy"] = False
    return job


@app.get("/api/evaluations")
def list_evaluations() -> dict:
    try:
        current = [dict(job, legacy=False) for job in evaluation_manager.list_jobs()]
        archived = evaluation_archive.list_reports()
    except LegacyArchiveError as exc:
        raise HTTPException(status_code=500, detail="歷史評測資料無法讀取") from exc
    evaluations = current + archived
    evaluations.sort(
        key=lambda item: item.get("created_at") or item.get("generated_at") or "",
        reverse=True,
    )
    return {"evaluations": evaluations}


@app.get("/api/evaluations/{run_id}")
def get_evaluation(run_id: str) -> dict:
    try:
        if run_id.startswith("legacy-"):
            return _legacy_detail(evaluation_archive.get_report(run_id))
        job = evaluation_manager.get_job(run_id)
        job["legacy"] = False
        return job
    except (EvaluationRunNotFoundError, LegacyReportNotFoundError) as exc:
        raise HTTPException(status_code=404, detail="找不到評測") from exc
    except (OSError, ValueError, json.JSONDecodeError, LegacyArchiveError) as exc:
        raise HTTPException(status_code=500, detail="評測資料損壞或無法讀取") from exc


@app.patch("/api/evaluations/{run_id}/results/{result_index}/review")
def review_evaluation_result(
    run_id: str,
    result_index: int,
    payload: EvaluationReviewRequest,
) -> dict:
    review = payload.model_dump(
        exclude={"target", "complete"},
        exclude_unset=True,
    )
    try:
        if run_id.startswith("legacy-"):
            report = evaluation_archive.update_review(
                run_id,
                result_index,
                payload.target,
                review,
                payload.complete,
            )
            return _legacy_detail(report)

        job = evaluation_manager.get_job(run_id)
        if job.get("status") != "completed":
            raise HTTPException(status_code=409, detail="評測尚未完成")
        updated = evaluation_manager.update_review(
            run_id,
            result_index,
            payload.target,
            review,
            payload.complete,
        )
        updated["legacy"] = False
        return updated
    except HTTPException:
        raise
    except (EvaluationRunNotFoundError, LegacyReportNotFoundError) as exc:
        raise HTTPException(status_code=404, detail="找不到評測") from exc
    except EvaluationResultNotFoundError as exc:
        raise HTTPException(status_code=404, detail="找不到評測結果") from exc
    except InvalidReviewError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except (OSError, ValueError, json.JSONDecodeError, LegacyArchiveError) as exc:
        raise HTTPException(status_code=500, detail="評測資料損壞或無法讀取") from exc


@app.get("/api/roles")
def roles() -> list[dict]:
    return [profile.to_dict() for profile in STUDENT_PROFILES]


@app.post("/api/sessions", status_code=201)
def create_session(payload: CreateSessionRequest) -> dict:
    return service.create_session(payload.topic, payload.objective)


@app.get("/api/sessions/{session_id}")
def get_session(session_id: str) -> dict:
    try:
        return service.snapshot(session_id)
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="找不到課堂") from exc


@app.post("/api/sessions/{session_id}/messages")
def send_message(session_id: str, payload: TeacherMessageRequest) -> dict:
    try:
        selected_provider = None
        if payload.model:
            try:
                installed_names = {item["name"] for item in ollama.installed_models()}
            except RuntimeError as exc:
                raise ValueError("Ollama 無法取得模型清單") from exc
            if payload.model not in installed_names:
                raise ValueError(f"模型未安裝或不可用：{payload.model}")
            selected_provider = ResilientProvider(
                primary=OllamaProvider(
                    base_url=ollama.base_url,
                    model=payload.model,
                    timeout=ollama.timeout,
                )
            )
        return service.send_teacher_message(
            session_id,
            payload.message,
            provider=selected_provider,
        )
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="找不到課堂") from exc
    except SessionClosedError as exc:
        raise HTTPException(status_code=409, detail="課堂已結束") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/sessions/{session_id}/finish")
def finish_session(session_id: str) -> dict:
    try:
        return service.finish_session(session_id)
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="找不到課堂") from exc

