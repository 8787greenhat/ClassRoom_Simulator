from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .db import Database
from .llm import OllamaProvider, ResilientProvider
from .roles import STUDENT_PROFILES
from .service import ClassroomService, SessionClosedError, SessionNotFoundError


BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
STATIC_DIR = BASE_DIR / "static"
DB_PATH = Path(os.getenv("CLASSROOM_DB_PATH", PROJECT_DIR / "data" / "classroom.db"))

ollama = OllamaProvider()
service = ClassroomService(Database(DB_PATH), ResilientProvider(primary=ollama))

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


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
def health() -> dict:
    return {
        "ok": True,
        "ollama_available": ollama.available(),
        "model": ollama.model,
        "fallback": "mock",
    }


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
        return service.send_teacher_message(session_id, payload.message)
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

