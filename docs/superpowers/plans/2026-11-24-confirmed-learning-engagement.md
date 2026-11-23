# Confirmed Learning and Engagement Implementation Plan

> **For agentic workers:** Implement natively in the primary session per `AGENTS.md`; do not dispatch subagents by default. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Require a successful student demonstration before learning-state changes and make bounded engagement/emotion state visibly affect student behavior.

**Architecture:** Stage deterministic teacher evidence before generation, then confirm it against an eligible student response before committing state changes. Persist role-specific engagement in the existing JSON column and expose the turn snapshot through BehaviorPlan and event metadata.

**Tech Stack:** Python dataclasses, SQLite JSON payload, existing FastAPI/static UI, `unittest`.

**Spec:** `docs/superpowers/specs/2026-11-24-confirmed-learning-engagement-design.md`

## Global Constraints

- Density unit only; no external evaluator or new dependency.
- No SQLite schema change; old rows and historical events remain readable.
- Deterministic rules and bounded one-level learning updates.
- Guarded and resilient fallback text cannot confirm learning.
- Run targeted tests during development and the full suite once before commit.

## Review Focus

- Teacher explanation without a correct student demonstration must not mutate learning state.
- A response about the wrong concept must not reduce another misconception.
- Guard/fallback output must not be mistaken for student evidence.
- Missing or malformed engagement JSON must recover to role defaults.
- Silent behavior must remain a valid observable event without breaking selection or persistence.

### Task 1: Two-stage learning confirmation

**Files:** `classroom_simulator/learning.py`, `classroom_simulator/service.py`, `classroom_simulator/llm.py`, `tests/test_learning.py`, `tests/test_service.py`

- [x] Add failing tests for staged evidence, successful/failed demonstration, mismatched concept and ineligible source.
- [x] Add `classify_student_demonstration()` and `confirm_learning_from_response()`; keep updates bounded and synchronize the legacy strength.
- [x] Integrate staging before generation and confirmation after reply; record distinct teacher and student metadata.
- [x] Allow a high-misconception role to attempt an explanation only when targeted evidence and an understanding check are present.
- [x] Run targeted learning/service/LLM tests.

### Task 2: Engagement state and visible behavior

**Files:** `classroom_simulator/engagement.py`, `classroom_simulator/models.py`, `classroom_simulator/db.py`, `classroom_simulator/behavior.py`, `classroom_simulator/llm.py`, matching tests.

- [x] Add failing tests for role defaults, clamp/recovery, persistence, silent and hesitant plans, and post-response changes.
- [x] Implement role defaults, projected turn state and deterministic post-response updates.
- [x] Persist `engagement` inside `concept_state_json` and expose it in StudentState/BehaviorPlan.
- [x] Add `silent` and `hesitant` behavior instructions, fallbacks and validation.
- [x] Run targeted engagement/behavior/DB tests.

### Task 3: Observation, regression and records

**Files:** `classroom_simulator/static/app.js`, `classroom_simulator/static/evaluation.js`, scenario/evaluation adapters if required, docs and tests.

- [x] Show compact engagement state in the classroom and new BehaviorPlan evidence without changing legacy report rendering.
- [x] Update the ten-turn mock expectations to require demonstrated understanding.
- [x] Bump Prompt version, add ADR and development log entry, and update architecture/roadmap/context.
- [x] Run UI/API targeted tests, Mock evaluation, Mock classroom scenario, then one full test suite and `git diff --check`.
- [x] Commit the verified batch; do not push unless explicitly requested.
