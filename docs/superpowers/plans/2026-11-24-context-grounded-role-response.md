# Context-Grounded Role Response Implementation Plan

> **For agentic workers:** Implement natively in the primary session per `AGENTS.md`; do not dispatch subagents by default. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make student replies answer the teacher's current move before applying role style, and retry replies that import an unrelated comparison condition.

**Architecture:** `behavior.py` owns deterministic teacher-move classification, response focus, tagged examples, and alignment checks. `llm.py` injects only matching examples and feeds alignment failures into the existing one-retry pipeline; no new model, dependency, API, or schema is added.

**Tech Stack:** Python dataclasses, existing Ollama/Mock providers, JavaScript evidence UI, `unittest`.

**Spec:** `docs/superpowers/specs/2026-11-24-context-grounded-role-response-design.md`

## Global Constraints

- Density unit only; no external judge, multi-agent call, fine-tuning, or new dependency.
- Keep exactly two synthetic examples per role, tagged by teacher move.
- Preserve raw/retried/guarded/fallback source separation and one retry maximum.
- Do not modify SQLite schema or historical evaluation reports.
- Use development cases only; do not tune against holdout v1.

## Review Focus

- Definition wording with multiple questions still classifies as definition.
- Teacher-provided same-mass/same-volume conditions remain legal in comparison questions.
- Unstated comparison conditions fail without rejecting ordinary uncertain student language.
- No matching example produces no cross-task example rather than an exception.
- Alignment failure remains visible in generation attempts and does not change misconception state.

### Task 1: Teacher move and BehaviorPlan grounding

**Files:** `classroom_simulator/models.py`, `classroom_simulator/behavior.py`, `tests/test_behavior.py`

- [ ] Add regression tests for the screenshot prompt, allowed comparison conditions, tagged-example selection and plan serialization.
- [ ] Implement `classify_teacher_move()`, `select_response_examples()` and `validate_question_alignment()`.
- [ ] Add `teacher_move`, `response_focus`, and `forbidden_assumptions` to BehaviorPlan and populate every behavior branch.
- [ ] Run behavior tests.

### Task 2: Generation, retry and deterministic providers

**Files:** `classroom_simulator/llm.py`, `tests/test_llm.py`, `tests/test_service.py`

- [ ] Add a scripted Ollama regression proving the screenshot answer fails first-attempt alignment and a contextual retry succeeds.
- [ ] Inject only matching tagged examples and include alignment failures in `_validation_failures()`.
- [ ] Make Mock definition replies role-appropriate and keep the second-failure contextual fallback observable as guarded.
- [ ] Bump Prompt to `density-v4.6` and run targeted LLM/service/evaluation tests.

### Task 3: Observation, research record and verification

**Files:** `classroom_simulator/static/evaluation.js`, project docs, UI/scenario tests.

- [ ] Show teacher move, response focus and forbidden assumptions in new BehaviorPlan evidence.
- [ ] Record research sources, ADR, development log and a 3B repeated development-case smoke without using holdout v1.
- [ ] Run Mock evaluation, Mock classroom scenario, API/UI smoke, one full test suite and `git diff --check`.
- [ ] Commit locally; do not push unless requested.
