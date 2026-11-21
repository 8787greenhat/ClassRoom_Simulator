# Evaluation Observatory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local evaluation observatory that starts background role evaluations, preserves versioned JSON reports, reads four important archived reports, and supports case-level human review from one web workspace.

**Architecture:** Keep evaluation generation in `evaluation.py`, add an in-process single-worker job manager backed by atomic JSON files, and normalize new and selected legacy reports behind FastAPI endpoints. A separate static page polls active jobs, filters cases, shows raw/final responses, and writes review overlays without modifying archived evidence or the classroom SQLite schema.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic, `concurrent.futures.ThreadPoolExecutor`, JSON files, SQLite unchanged, vanilla HTML/CSS/JavaScript, `unittest`.

**Spec:** `docs/superpowers/specs/2026-11-22-evaluation-observatory-design.md`

**Execution status:** Tasks 1–2 completed on 2026-11-22. Tasks 3–6 are paused at the user's request and should resume from Task 3.

## Global Constraints

- Keep the research scope on junior-high density; do not add RAG, peer interaction, teacher scoring, or new curriculum units.
- Do not change the `sessions`, `student_states`, or `events` SQLite schema.
- Preserve existing CLI entry points for `evaluation.py` and `classroom_scenario.py`.
- A hard pass rate is only marker/length/safety evidence; UI copy must not call it semantic accuracy or student realism.
- Holdout v1 is already used; label it read-only for reproduction and human review, never as a tuning target.
- New web single-turn Ollama runs use `OllamaProvider`; per-item failures stay `error` and do not fall back to Mock.
- Run at most one background evaluation at a time.
- Do not write reviews into tracked files under `docs/evaluations/results/`.
- Do not introduce a 1–5 expert scale; use `yes`/`no`/`uncertain` and notes until a separate user decision.
- Keep all tests independent of Ollama and network access.

## Review Focus

- A malformed or partially written job/report JSON must not break the whole history list; Task 2 adds a corrupted-file test.
- A legacy report with an unknown evaluator/scenario id must show missing provenance instead of borrowing current scenario text; Task 3 adds a catalog-mismatch test.
- Server restart and concurrent creation must not duplicate experiments; Task 2 tests `interrupted` recovery and one-active-job rejection.
- An invalid/uninstalled Ollama model must be rejected before a job is created, while a provider runtime failure becomes an `error` row; Tasks 1 and 4 test both paths.
- Human review completion must distinguish applicable raw/final targets and survive reload without altering evidence; Tasks 2 and 3 test new and legacy persistence.

---

## File Structure

### Create

- `classroom_simulator/evaluation_jobs.py` — atomic JSON storage, single background worker, job lifecycle, new-report review updates.
- `classroom_simulator/evaluation_archive.py` — fixed legacy manifest loading, versioned scenario enrichment, adapters, review overlays.
- `classroom_simulator/static/evaluation.html` — observatory page shell.
- `classroom_simulator/static/evaluation.js` — API calls, polling, filters, case selection, review actions.
- `classroom_simulator/static/evaluation.css` — responsive observatory layout.
- `docs/evaluations/observatory-manifest.json` — exactly four approved archived report entries.
- `docs/evaluations/legacy-scenarios-evaluator-2.1.json` — version-pinned baseline/holdout scenario evidence.
- `tests/test_evaluation_jobs.py` — storage, lifecycle, concurrency, restart, review tests.
- `tests/test_evaluation_archive.py` — manifest, adapters, provenance, overlay tests.
- `tests/test_evaluation_api.py` — observatory HTTP contract tests.
- `tests/test_evaluation_ui.py` — static UI contract and safety-copy tests.

### Modify

- `classroom_simulator/models.py` — add optional Guard-before text to `AgentReply`.
- `classroom_simulator/llm.py` — capture normalized text before role/behavior/length guards.
- `classroom_simulator/evaluation.py` — report schema v2, scenario evidence, target-aware review template, progress callback.
- `classroom_simulator/main.py` — manager wiring, request models, observatory route and APIs.
- `tests/test_llm.py` — raw/final response invariants.
- `tests/test_evaluation.py` — report v2 and progress/error behavior.
- `.gitignore` — ignore `.superpowers/` and local `data/evaluations/` runtime artifacts.
- `docs/ARCHITECTURE.md` — new components, storage and request flow.
- `docs/ROADMAP.md` — place observability/human annotation before more Prompt tuning.
- `docs/DECISIONS.md` — record local background jobs + JSON/overlay decision.
- `docs/TESTING.md` — observatory test and smoke commands.
- `docs/DEVELOPMENT_LOG.md` — completed batch, verification and unresolved limits.

---

### Task 1: Report v2 and Guard-before response contract

**Files:**
- Modify: `classroom_simulator/models.py`
- Modify: `classroom_simulator/llm.py`
- Modify: `classroom_simulator/evaluation.py`
- Modify: `tests/test_llm.py`
- Modify: `tests/test_evaluation.py`

**Interfaces:**
- Produces: `AgentReply.raw_response: str | None`.
- Produces: `evaluate_provider(..., progress_callback: Callable[[int, int], None] | None = None) -> dict`.
- Produces: report schema `2.0` with scenario evidence, `raw_response`, final `response`, and target-aware `human_review`.
- Produces: `pending_review() -> dict` and `build_human_review(source_category: str, raw_response: str | None) -> dict` for Tasks 2–3.

- [ ] **Step 1: Write failing `tests/test_llm.py` cases for raw/final response invariants**

Add tests proving an unguarded Mock reply has `raw_response == response`, and a deliberately guarded Ollama-path reply retains pre-Guard normalized text while `response` contains the final guarded text.

- [ ] **Step 2: Run the focused LLM tests and confirm failure**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_llm -v`

Expected: FAIL because `AgentReply.raw_response` does not exist.

- [ ] **Step 3: Add `raw_response` and capture it before all guards**

In `models.py`, add `raw_response: str | None = None` to `AgentReply`. In `OllamaProvider.reply()`, assign normalized parsed text to `raw_response` before `enforce_role_consistency`, `enforce_behavior_consistency`, and `enforce_response_length`; return it unchanged in the `AgentReply`. In `MockProvider.reply()`, set `raw_response` to the deterministic final response.

- [ ] **Step 4: Run LLM tests and confirm they pass**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_llm -v`

Expected: PASS.

- [ ] **Step 5: Write failing report-v2 tests in `tests/test_evaluation.py`**

Assert:

- `report_schema_version == "2.0"`.
- Every result embeds `teacher_message`, `misconception_strength`, `expected_markers`, `forbidden_markers`, `raw_response`, and final `response`.
- `raw_ollama`/`mock` rows need only `human_review.delivered`.
- A guarded stub provider with distinct raw/final text has both `human_review.delivered` and `human_review.raw_model` pending.
- An error row has no review targets.
- A progress callback receives monotonic `(completed, total)` pairs ending at `(total, total)`.
- A runtime provider error remains `source_category == "error"`, not fallback.

- [ ] **Step 6: Run focused evaluation tests and confirm failure**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_evaluation -v`

Expected: FAIL on missing v2 fields and callback.

- [ ] **Step 7: Implement report v2 and progress callback**

Use this exact signature in `evaluation.py`:

```python
def evaluate_provider(
    provider: LLMProvider,
    scenarios: Iterable[EvaluationScenario] = SCENARIOS,
    repeats: int = 1,
    suite_name: str = "baseline",
    progress_callback: Callable[[int, int], None] | None = None,
) -> dict:
```

Call the callback once after appending each result. Replace the flat pending template with target-aware `human_review`, and derive report-level pending/completed target and result counts without assigning a semantic score.

- [ ] **Step 8: Run focused and regression tests**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_llm tests.test_evaluation tests.test_classroom_scenario -v`

Expected: PASS.

- [ ] **Step 9: Commit the report contract**

```powershell
git add classroom_simulator/models.py classroom_simulator/llm.py classroom_simulator/evaluation.py tests/test_llm.py tests/test_evaluation.py
git commit -m "feat: preserve raw evaluation responses"
```

---

### Task 2: Atomic JSON job store and background lifecycle

**Files:**
- Create: `classroom_simulator/evaluation_jobs.py`
- Create: `tests/test_evaluation_jobs.py`

**Interfaces:**
- Consumes: Task 1 `evaluate_provider()` progress callback and report v2.
- Produces: `EvaluationJobRequest(provider: str, suite: str, model: str | None, repeats: int)`.
- Produces: `EvaluationJobManager(root: Path, runner: EvaluationRunner, executor: Executor | None = None)`.
- Produces: `create_job(request) -> dict`, `list_jobs() -> list[dict]`, `get_job(run_id) -> dict`, `update_review(run_id, result_index, target, review, complete) -> dict`, `shutdown() -> None`.
- Produces: `EvaluationBusyError`, `EvaluationRunNotFoundError`, `EvaluationResultNotFoundError`, and `InvalidReviewError`.

- [ ] **Step 1: Write failing storage/lifecycle tests**

Cover creation (`queued → running → completed`), monotonic progress, generated safe run ids, `job.json`/`report.json`, one-active-job rejection, runner failure to `failed`, startup recovery to `interrupted`, newest-first listing, unknown id, corrupted JSON isolation, and executor shutdown.

- [ ] **Step 2: Run the new tests and confirm failure**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_evaluation_jobs -v`

Expected: import failure because `evaluation_jobs.py` does not exist.

- [ ] **Step 3: Implement atomic storage and job state transitions**

Use `ThreadPoolExecutor(max_workers=1)` by default. Write JSON to a sibling temporary file, flush/close it, then call `Path.replace()` onto the final file. Protect active-job and review mutations with a lock. Do not expose arbitrary paths through any public method.

- [ ] **Step 4: Run storage/lifecycle tests and confirm pass**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_evaluation_jobs -v`

Expected: PASS.

- [ ] **Step 5: Write failing target-aware review persistence tests**

Assert draft saves remain pending; completing requires all three fields in `{yes, no, uncertain}`; raw-model target is rejected when unavailable; delivered/raw targets count independently; review reload survives a new manager instance; notes do not alter hard scores.

- [ ] **Step 6: Implement `update_review()` and report counters**

Allow only `directly_answers_teacher_request`, `role_consistency`, `student_realism`, `notes`, `status`, and `reviewed_at`. Ignore no unknown fields—raise `InvalidReviewError`. Set `reviewed_at` in UTC only when completing.

- [ ] **Step 7: Run Task 2 tests and the Task 1 regression subset**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_evaluation_jobs tests.test_evaluation -v`

Expected: PASS.

- [ ] **Step 8: Commit the job manager**

```powershell
git add classroom_simulator/evaluation_jobs.py tests/test_evaluation_jobs.py
git commit -m "feat: add background evaluation jobs"
```

---

### Task 3: Selected legacy reports and review overlays

**Files:**
- Create: `classroom_simulator/evaluation_archive.py`
- Create: `docs/evaluations/observatory-manifest.json`
- Create: `docs/evaluations/legacy-scenarios-evaluator-2.1.json`
- Create: `tests/test_evaluation_archive.py`

**Interfaces:**
- Consumes: Task 1 review template/report-view field names.
- Produces: `LegacyEvaluationArchive(project_dir: Path, overlay_dir: Path)`.
- Produces: `list_reports() -> list[dict]`, `get_report(report_id: str) -> dict`, and `update_review(report_id, result_index, target, review, complete) -> dict`.
- Produces: normalized reports with `legacy: True`, `report_type` (`single_turn` or `full_classroom`), `capabilities`, and missing fields represented as `None` plus an explicit capability flag.

- [ ] **Step 1: Write the fixed manifest and versioned scenario catalog**

Manifest entries must reference only:

- `results/2026-11-10-qwen2.5-3b-density-v4-2-ab.json`
- `results/2026-11-10-qwen2.5-7b-density-v4-2-ab.json`
- `results/2026-11-10-qwen2.5-3b-density-holdout-v1.json`
- `results/2026-11-10-full-classroom-density-v4-2-run1.json`

The catalog must snapshot evaluator `2.1` baseline and holdout ids, teacher messages, misconception strength, expected markers, and forbidden markers from the approved `743e806` baseline.

- [ ] **Step 2: Write failing archive discovery/normalization tests**

Assert exactly four entries, manifest path confinement under `docs/evaluations/`, single-turn scenario enrichment from matching evaluator/catalog, full-classroom `turns` normalization, `raw_response` capability false for old guarded rows, and stable newest-first summaries.

- [ ] **Step 3: Run archive tests and confirm failure**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_evaluation_archive -v`

Expected: import failure because `evaluation_archive.py` does not exist.

- [ ] **Step 4: Implement manifest loading and two explicit adapters**

Do not scan arbitrary JSON files. Resolve manifest paths, require them to remain under the approved archive root, compute a SHA-256 content hash, and select only the declared `single_turn_v2_1` or `full_classroom_v4_2` adapter.

- [ ] **Step 5: Write failing provenance/overlay tests**

Cover unknown scenario id, evaluator mismatch, missing archive file, malformed archived JSON, content-hash mismatch invalidating an existing overlay, no writes to archive files, draft/completed reviews, and unavailable raw-model review rejection.

- [ ] **Step 6: Implement review overlays**

Store overlays at `data/evaluations/legacy-reviews/<report-id>.json` through the provided `overlay_dir`. Include archive relative path, SHA-256, result indexes, targets, and review payloads. Merge overlays only when both path and hash match.

- [ ] **Step 7: Run archive tests**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_evaluation_archive -v`

Expected: PASS.

- [ ] **Step 8: Commit the archive adapter**

```powershell
git add classroom_simulator/evaluation_archive.py docs/evaluations/observatory-manifest.json docs/evaluations/legacy-scenarios-evaluator-2.1.json tests/test_evaluation_archive.py
git commit -m "feat: expose selected evaluation archives"
```

---

### Task 4: FastAPI evaluation endpoints

**Files:**
- Modify: `classroom_simulator/main.py`
- Create: `tests/test_evaluation_api.py`

**Interfaces:**
- Consumes: Task 2 `EvaluationJobManager` and Task 3 `LegacyEvaluationArchive`.
- Produces: `GET /evaluations`, `POST /api/evaluations`, `GET /api/evaluations`, `GET /api/evaluations/{run_id}`, and `PATCH /api/evaluations/{run_id}/results/{result_index}/review`.
- Produces: `EvaluationCreateRequest` and `EvaluationReviewRequest` Pydantic models.

- [ ] **Step 1: Write failing API tests for Mock execution and history**

Patch module-level manager/archive with temporary instances. Assert `GET /evaluations` serves the page; `POST` returns 202; polling reaches completed; list includes new and four legacy reports without full results; detail returns normalized report; `/api/health` and classroom endpoints remain usable.

- [ ] **Step 2: Run API tests and confirm failure**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_evaluation_api -v`

Expected: 404/import failure for observatory routes.

- [ ] **Step 3: Wire environment paths and the Mock runner**

Use `EVALUATION_DATA_DIR`, defaulting to `PROJECT_DIR / "data" / "evaluations"`. The runner maps `suite` through `SCENARIO_SUITES`, creates `MockProvider` or direct `OllamaProvider`, and calls Task 1 `evaluate_provider()` with progress.

- [ ] **Step 4: Implement list/detail/create routes and exception mapping**

Return 202 for create, 409 for an active job, 404 for missing ids/results, and 422 for invalid request/review fields. Merge new and legacy summaries in the list route. Never return local absolute paths or tracebacks.

- [ ] **Step 5: Write failing validation/review API tests**

Cover invalid provider/suite/repeats, Mock with model, Ollama without/uninstalled model, safe run ids, runner RuntimeError recorded as an error row, applicable/unavailable review targets, draft vs complete, and corrupted report detail.

- [ ] **Step 6: Implement model validation and review PATCH routing**

Validate Ollama models using the same installed-model source as `/api/models` before creating the job. Route review updates to the job manager or archive by id prefix/registry metadata, not by client-supplied path.

- [ ] **Step 7: Run API and regression tests**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_evaluation_api tests.test_api tests.test_service -v`

Expected: PASS.

- [ ] **Step 8: Commit the API**

```powershell
git add classroom_simulator/main.py tests/test_evaluation_api.py
git commit -m "feat: add evaluation observatory API"
```

---

### Task 5: Single-page observatory UI

**Files:**
- Create: `classroom_simulator/static/evaluation.html`
- Create: `classroom_simulator/static/evaluation.js`
- Create: `classroom_simulator/static/evaluation.css`
- Create: `tests/test_evaluation_ui.py`
- Modify: `classroom_simulator/static/index.html`

**Interfaces:**
- Consumes: Task 4 HTTP endpoints and normalized report fields.
- Produces: researcher workflow for run creation, progress polling, report selection, filters, raw/final inspection, and review persistence.

- [ ] **Step 1: Write failing static UI contract tests**

Assert the page links its CSS/JS; has accessible controls for provider, suite, model, repeats, history, filters, case list, detail, review target, three review judgments, notes, draft and complete actions; includes holdout and shared-Ollama warnings; and avoids wording that calls hard pass rate accuracy/realism.

- [ ] **Step 2: Run UI tests and confirm failure**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_evaluation_ui -v`

Expected: missing static files.

- [ ] **Step 3: Build the responsive page shell and navigation**

Implement the approved single-workspace layout with semantic HTML, keyboard-accessible native controls, mobile stacking below the desktop two-pane workspace, a link back to `/`, and a link from the classroom page to `/evaluations`.

- [ ] **Step 4: Implement API state, history and active-job polling**

In `evaluation.js`, keep one state object for runs, selected run/result, filters and pending edits. Poll only while the selected/new job is queued or running; stop on completed/failed/interrupted or page unload. Disable a second start while an active job exists.

- [ ] **Step 5: Implement case filtering and evidence detail**

Support source, hard-pass, role and review-status filters. Render missing legacy fields as「舊報告未保存」. Show hard checks independently from human review. For holdout v1, keep the used-holdout warning visible.

- [ ] **Step 6: Implement target-aware review editing**

For guarded rows with raw text, provide separate raw-model and delivered targets; otherwise show only delivered. Support save draft and complete-and-next, retain unsaved form values after an API failure, and reflect updated counters after success.

- [ ] **Step 7: Run UI, API and full automated tests**

Run: `.\.venv\Scripts\python.exe -m unittest discover -s tests -v`

Expected: all tests pass.

- [ ] **Step 8: Commit the UI**

```powershell
git add classroom_simulator/static/evaluation.html classroom_simulator/static/evaluation.js classroom_simulator/static/evaluation.css classroom_simulator/static/index.html tests/test_evaluation_ui.py
git commit -m "feat: add evaluation observatory workspace"
```

---

### Task 6: Documentation, smoke verification and development log

**Files:**
- Modify: `.gitignore`
- Modify: `docs/ARCHITECTURE.md`
- Modify: `docs/ROADMAP.md`
- Modify: `docs/DECISIONS.md`
- Modify: `docs/TESTING.md`
- Modify: `docs/DEVELOPMENT_LOG.md`

**Interfaces:**
- Consumes: completed Tasks 1–5 and their observed verification results.
- Produces: reproducible commands, decision/history records, clean Git status and final evidence.

- [ ] **Step 1: Add local runtime ignores**

Ignore `.superpowers/` and `data/evaluations/` while preserving `data/.gitkeep`. Verify the existing companion mockup no longer appears in `git status`.

- [ ] **Step 2: Update architecture, roadmap and testing docs**

Document the job manager, archive adapter, API flow, storage paths, report/review semantics, holdout warning, test commands and UI smoke path. Place the observatory/human annotation milestone before further Prompt tuning and RAG.

- [ ] **Step 3: Add an ADR for local jobs and immutable archive overlays**

Record the chosen in-process single-worker + JSON approach, the reason SQLite schema stays unchanged, archive immutability, tradeoffs on restart/interruption and the future trigger for adopting a real queue.

- [ ] **Step 4: Run all mandatory automated checks**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m classroom_simulator.evaluation --provider mock
.\.venv\Scripts\python.exe -m classroom_simulator.classroom_scenario --provider mock
git diff --check
```

Expected: all tests and both Mock workflows pass; no whitespace errors.

- [ ] **Step 5: Run API smoke with isolated data paths**

Start `run.ps1` with temporary `CLASSROOM_DB_PATH` and `EVALUATION_DATA_DIR`. Verify `/api/health`, `/evaluations`, Mock job creation, progress completion, report retrieval, review save/reload, and classroom create/message/finish. Stop the server and remove only the explicitly created temporary directory.

- [ ] **Step 6: Run browser smoke**

Verify desktop and narrow layouts; start a Mock run; observe progress; select each of the four legacy reports; filter cases; inspect missing raw text; save/reload delivered review; and confirm holdout/shared-Ollama warnings. Record only observed results.

- [ ] **Step 7: Write the completed development-log entry**

Add date, purpose, changed modules, exact test counts and commands, API/UI smoke outcomes, preserved limitations, and unresolved items. Do not claim Ollama quality improvement or expert-score validity.

- [ ] **Step 8: Review tracked files for data safety**

Run `git status --short` and inspect staged names. Confirm no `.env`, database, local job/review JSON, transcript, secret or personal data is tracked.

- [ ] **Step 9: Commit documentation and verification records**

```powershell
git add .gitignore docs/ARCHITECTURE.md docs/ROADMAP.md docs/DECISIONS.md docs/TESTING.md docs/DEVELOPMENT_LOG.md docs/superpowers/specs/2026-11-22-evaluation-observatory-design.md docs/superpowers/plans/2026-11-22-evaluation-observatory.md
git commit -m "docs: record evaluation observatory rollout"
```

---

## Self-Review Result

- Spec coverage: all goals, non-goals, storage, legacy data, review targets, API/UI, recovery, tests and documentation map to Tasks 1–6.
- Step granularity: every task follows failing test → focused implementation → verification → commit; no production task begins without a pinned behavior.
- Type consistency: `raw_response`, `human_review.delivered`, `human_review.raw_model`, `EvaluationJobRequest`, job-manager methods and archive methods are named once and consumed consistently.
- Review focus: corrupted files, legacy provenance, job restart/concurrency, model errors and target-aware review each have an owning test task.
- Proportion: implementation bodies are left to executors; the plan fixes interfaces, invariants, commands and evidence without reproducing the program.
