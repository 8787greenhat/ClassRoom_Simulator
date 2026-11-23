# Concept State and Evidence-Grounded Learning Implementation Plan

> **Project execution override:** Follow `AGENTS.md`: implement directly in the primary agent with token-efficient reads; do not invoke executing-plans, subagents, or per-task reviewers.

**Goal:** Persist five density concept mastery levels and two named misconception beliefs, then update only the concepts directly supported and checked by teacher evidence.

**Architecture:** A focused `learning.py` owns concept keys, role initial states, deterministic evidence classification and bounded updates. SQLite stores the structured state in one backward-compatible JSON column; `BehaviorPlan` consumes it and existing scalar misconception strength remains a compatibility mirror.

**Tech Stack:** Python dataclasses, SQLite JSON text, unittest, existing FastAPI/event metadata.

**Spec:** `docs/superpowers/specs/2026-11-23-concept-state-evidence-design.md`

## Global Constraints

- No destructive migration, dependency, RAG, external API or holdout tuning.
- All levels remain integers from 0 through 3 and change by at most one per teacher turn.
- Prompt becomes `density-v4.4`; evaluator remains `2.1`.
- Existing sessions, reports and `misconception_strength` consumers remain compatible.

## Review Focus

- Existing database rows with no JSON state must receive role defaults without data loss.
- Generic correction and praise must not change mastery or belief.
- Evidence for one misconception must not lower an unrelated belief.
- Repeated targeted evidence must change each value by at most one and clamp to 0–3.
- Event evidence must describe exactly the state that was persisted and sent to the model.

### Task 1: Concept model and evidence updater

**Files:** create `classroom_simulator/learning.py`; modify `models.py`, `roles.py`; create `tests/test_learning.py`

- [x] Define concept/belief keys, role initial values and `apply_teacher_evidence(...)` with an auditable result dictionary.
- [x] Extend `StudentState` and `BehaviorPlan`; test initialization, targeted, generic and misaligned evidence.

### Task 2: Backward-compatible persistence

**Files:** modify `db.py`; create `tests/test_concept_state_db.py`

- [x] Add and migrate `concept_state_json`, populate new sessions and round-trip updates.
- [x] Test a manually created legacy row and confirm role defaults plus existing scalar values survive.

### Task 3: Classroom and generation integration

**Files:** modify `service.py`, `behavior.py`, `evaluation.py`, `classroom_scenario.py`, related tests

- [x] Replace scalar keyword update with evidence-grounded state update and save its audit data in teacher/student event metadata.
- [x] Feed state into `BehaviorPlan`, initialize evaluation states, bump Prompt to density-v4.4 and preserve ten-turn expectations.
- [x] Run only affected tests, then Mock evaluation and classroom scenario.

### Task 4: Documentation and final verification

**Files:** update `AGENTS.md`, architecture, decisions, roadmap, testing and development log

- [x] Record schema migration, data meaning, evidence limits and version change.
- [x] Run the full suite once, smoke the running platform, inspect diff and commit without pushing.
