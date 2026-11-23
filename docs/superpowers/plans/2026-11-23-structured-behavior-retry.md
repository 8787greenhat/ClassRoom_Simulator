# Structured Behavior Planning and Guard Retry Implementation Plan

> **Project execution override:** Follow `AGENTS.md`: the primary agent implements directly with token-efficient reads; do not invoke executing-plans, subagents, or per-task reviewers. Use one targeted verification cycle and one full suite at the end.

**Goal:** Add structured student behavior plans, one bounded Ollama regeneration, two curated examples per role, and observable attempt evidence.

**Architecture:** Extend the existing behavior planner rather than replacing it. Ollama receives a serialized plan and role examples, validates the first response with existing guards, retries once with failure feedback, then uses the existing deterministic rewrite only if the retry also fails.

**Tech Stack:** Python dataclasses, urllib/Ollama chat API, FastAPI event metadata, JSON evaluation reports, vanilla JavaScript observatory.

**Spec:** `docs/superpowers/specs/2026-11-23-structured-behavior-retry-design.md`

## Global Constraints

- No SQLite schema change and no new dependency.
- Preserve legacy evaluation archive compatibility.
- Prompt version becomes `density-v4.3`; evaluator remains `2.1`.
- Do not use holdout v1 for tuning or claim realism improvement without human review.

## Review Focus

- First valid response must not make a second HTTP request.
- Retry success must not be mislabeled as raw model or deterministic Guard success.
- Two failed attempts must preserve both texts before deterministic fallback.
- Mock and resilient fallback behavior must remain deterministic and compatible.
- Old reports without plan or attempts must still render.

### Task 1: Structured behavior plan and examples

**Files:** `classroom_simulator/models.py`, `classroom_simulator/behavior.py`, `tests/test_behavior.py`

- [x] Add serializable `BehaviorPlan` and `build_behavior_plan(...)`, keeping `plan_student_behavior(...)` as a compatibility wrapper.
- [x] Add exactly two curated synthetic examples for every role and test plan fields, role distinctions and example counts.

### Task 2: Bounded Ollama retry

**Files:** `classroom_simulator/llm.py`, `tests/test_llm.py`

- [x] Factor one Ollama chat attempt, inject the plan/examples, and collect validation failures.
- [x] Retry exactly once after a failed first response; return `ollama-retried` when retry passes and existing guarded output when both attempts fail.
- [x] Preserve attempts, retry reasons, plan and final source in `AgentReply`; test zero-retry, retry-success and retry-fallback paths.

### Task 3: Evidence propagation and observatory

**Files:** `classroom_simulator/service.py`, `classroom_simulator/evaluation.py`, `classroom_simulator/classroom_scenario.py`, `classroom_simulator/static/evaluation.html`, `classroom_simulator/static/evaluation.js`, related tests

- [x] Save behavior plan, generation attempts and retry count without changing the database schema.
- [x] Add backward-compatible `retried` source classification and render attempts only when present.
- [x] Run affected behavior, LLM, evaluation, service and UI tests.

### Task 4: Documentation and final verification

**Files:** `AGENTS.md`, `docs/ARCHITECTURE.md`, `docs/DECISIONS.md`, `docs/DEVELOPMENT_LOG.md`, `docs/TESTING.md`

- [x] Document `density-v4.3`, bounded retry semantics, synthetic example limitation and observable evidence.
- [x] Run the full unittest suite once, run `git diff --check`, inspect the final diff, then commit without pushing.
