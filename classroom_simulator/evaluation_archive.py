from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from .evaluation import pending_review
from .evaluation_jobs import EvaluationResultNotFoundError, InvalidReviewError


class LegacyArchiveError(RuntimeError):
    pass


class LegacyReportNotFoundError(LookupError):
    pass


class LegacyEvaluationArchive:
    def __init__(self, project_dir: Path, overlay_dir: Path):
        self.project_dir = Path(project_dir)
        self.archive_dir = self.project_dir / "docs" / "evaluations"
        self.manifest_path = self.archive_dir / "observatory-manifest.json"
        self.overlay_dir = Path(overlay_dir)

    def list_reports(self) -> list[dict]:
        summaries = []
        for entry in self._manifest_entries():
            report = self._load_entry(entry)
            summaries.append({key: value for key, value in report.items() if key != "results"})
        return sorted(summaries, key=lambda item: item.get("generated_at") or "", reverse=True)

    def get_report(self, report_id: str) -> dict:
        for entry in self._manifest_entries():
            if entry.get("id") == report_id:
                return self._load_entry(entry)
        raise LegacyReportNotFoundError(report_id)

    def update_review(
        self,
        report_id: str,
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

        report = self.get_report(report_id)
        results = report["results"]
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
        current["reviewed_at"] = datetime.now(timezone.utc).isoformat() if complete else None

        overlay = self._matching_overlay(report) or {
            "report_id": report_id,
            "archive": dict(report["archive"]),
            "reviews": {},
        }
        overlay["reviews"].setdefault(str(result_index), {})[target] = current
        self._write_overlay(report_id, overlay)
        return self.get_report(report_id)

    def _manifest_entries(self) -> list[dict]:
        manifest = self._read_json(self.manifest_path, "manifest")
        entries = manifest.get("reports")
        if not isinstance(entries, list):
            raise LegacyArchiveError("legacy manifest reports must be a list")
        seen = set()
        for entry in entries:
            report_id = entry.get("id") if isinstance(entry, dict) else None
            if not report_id or report_id in seen:
                raise LegacyArchiveError("legacy manifest report ids must be unique")
            seen.add(report_id)
            self._resolve_archive_path(entry.get("path"))
        return entries

    def _load_entry(self, entry: dict) -> dict:
        report_path = self._resolve_archive_path(entry.get("path"))
        try:
            source_bytes = report_path.read_bytes()
        except OSError as exc:
            raise LegacyArchiveError(f"legacy report is missing: {entry['id']}") from exc
        try:
            source = json.loads(source_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise LegacyArchiveError(f"legacy report is unreadable: {entry['id']}") from exc
        digest = hashlib.sha256(source_bytes).hexdigest()
        adapter = entry.get("adapter")
        if adapter == "single_turn_v2_1":
            report = self._adapt_single_turn(entry, source, digest)
            return self._merge_overlay(report)
        if adapter == "full_classroom_v4_2":
            report = self._adapt_full_classroom(entry, source, digest)
            return self._merge_overlay(report)
        raise LegacyArchiveError(f"unsupported legacy adapter: {adapter}")

    def _adapt_single_turn(self, entry: dict, source: dict, digest: str) -> dict:
        expected_evaluator = entry.get("expected_evaluator_version")
        expected_suite = entry.get("expected_suite")
        if source.get("evaluator_version") != expected_evaluator:
            raise LegacyArchiveError(f"evaluator version mismatch: {entry['id']}")
        if source.get("suite") != expected_suite:
            raise LegacyArchiveError(f"suite mismatch: {entry['id']}")

        catalog_path = self._resolve_archive_path(entry.get("scenario_catalog"))
        catalog = self._read_json(catalog_path, "scenario catalog")
        binding = {
            "evaluator_version": expected_evaluator,
            "suite": expected_suite,
        }
        if binding not in catalog.get("report_bindings", []):
            raise LegacyArchiveError(f"scenario catalog binding mismatch: {entry['id']}")
        suite_scenarios = catalog.get("suites", {}).get(expected_suite)
        if not isinstance(suite_scenarios, list):
            raise LegacyArchiveError(f"scenario catalog suite missing: {expected_suite}")
        scenarios = {scenario["id"]: scenario for scenario in suite_scenarios}

        results = []
        for index, item in enumerate(source.get("results", [])):
            scenario = scenarios.get(item.get("scenario_id"))
            if scenario is None:
                raise LegacyArchiveError(f"unknown legacy scenario: {item.get('scenario_id')}")
            normalized = dict(item)
            normalized.update(
                {
                    "result_index": index,
                    "teacher_message": scenario["teacher_message"],
                    "misconception_strength": scenario["misconception_strength"],
                    "expected_markers": list(scenario["expected_markers"]),
                    "forbidden_markers": list(scenario["forbidden_markers"]),
                    "raw_response": None,
                    "error": item.get("error"),
                    "human_review": self._delivered_review(item.get("human_review")),
                }
            )
            results.append(normalized)

        return self._base_report(
            entry,
            source,
            digest,
            report_type="single_turn",
            results=results,
            summary={
                "total_runs": source.get("total_runs", len(results)),
                "passed_runs": source.get("passed_runs"),
                "pass_rate": source.get("pass_rate"),
                "source_usage": source.get("source_usage", {}),
                "latency_seconds": source.get("latency_seconds"),
            },
            scenario_evidence=True,
        )

    def _adapt_full_classroom(self, entry: dict, source: dict, digest: str) -> dict:
        if source.get("scenario_version") != entry.get("expected_scenario_version"):
            raise LegacyArchiveError(f"scenario version mismatch: {entry['id']}")
        results = []
        for index, turn in enumerate(source.get("turns", [])):
            results.append(
                {
                    "result_index": index,
                    "scenario_id": turn.get("id"),
                    "role_id": turn.get("actual_role_id"),
                    "teacher_message": turn.get("teacher_message"),
                    "misconception_strength": turn.get("misconception_strength"),
                    "expected_role_id": turn.get("expected_role_id"),
                    "expected_behavior_type": turn.get("expected_behavior_type"),
                    "expected_markers": None,
                    "forbidden_markers": None,
                    "run": 1,
                    "provider": turn.get("provider"),
                    "behavior_type": turn.get("behavior_type"),
                    "guarded": turn.get("guarded", False),
                    "guard_reason": turn.get("guard_reason"),
                    "source_category": turn.get("source_category"),
                    "raw_response": None,
                    "response": turn.get("response", ""),
                    "error": None,
                    "latency_seconds": None,
                    "human_review": self._delivered_review(turn.get("human_review")),
                    "passed": turn.get("passed", False),
                    "checks": turn.get("checks", {}),
                    "forbidden_hits": [],
                    "response_length": turn.get("response_length", 0),
                }
            )
        return self._base_report(
            entry,
            source,
            digest,
            report_type="full_classroom",
            results=results,
            summary=dict(source.get("summary", {})),
            scenario_evidence=True,
        )

    def _base_report(
        self,
        entry: dict,
        source: dict,
        digest: str,
        report_type: str,
        results: list[dict],
        summary: dict,
        scenario_evidence: bool,
    ) -> dict:
        return {
            "run_id": entry["id"],
            "title": entry.get("title", entry["id"]),
            "legacy": True,
            "status": "completed",
            "report_type": report_type,
            "generated_at": source.get("generated_at"),
            "prompt_version": source.get("prompt_version"),
            "evaluator_version": source.get("evaluator_version"),
            "suite": source.get("suite"),
            "provider_config": source.get("provider_config", {}),
            "used_holdout": bool(entry.get("used_holdout", False)),
            "summary": summary,
            "human_review_status": self._review_status(results),
            "capabilities": {
                "raw_response": False,
                "scenario_evidence": scenario_evidence,
                "review_overlay": True,
                "review_overlay_stale": False,
            },
            "archive": {
                "relative_path": entry["path"],
                "sha256": digest,
            },
            "results": results,
        }

    @staticmethod
    def _delivered_review(legacy_review: dict | None) -> dict:
        review = pending_review()
        review["reviewed_at"] = None
        if isinstance(legacy_review, dict):
            for field in review:
                if field in legacy_review:
                    review[field] = legacy_review[field]
        return {"delivered": review}

    @staticmethod
    def _review_status(results: list[dict]) -> dict:
        targets = [
            review
            for result in results
            for review in result.get("human_review", {}).values()
        ]
        completed_targets = sum(review.get("status") == "completed" for review in targets)
        completed_results = sum(
            bool(result.get("human_review"))
            and all(
                review.get("status") == "completed"
                for review in result["human_review"].values()
            )
            for result in results
        )
        reviewable_results = sum(bool(result.get("human_review")) for result in results)
        return {
            "results": {
                "pending": reviewable_results - completed_results,
                "completed": completed_results,
            },
            "targets": {
                "pending": len(targets) - completed_targets,
                "completed": completed_targets,
            },
        }

    def _resolve_archive_path(self, relative_path: str | None) -> Path:
        if not isinstance(relative_path, str) or not relative_path:
            raise LegacyArchiveError("legacy archive path is required")
        archive_root = self.archive_dir.resolve()
        candidate = (self.archive_dir / relative_path).resolve()
        try:
            candidate.relative_to(archive_root)
        except ValueError as exc:
            raise LegacyArchiveError("legacy archive path escapes archive directory") from exc
        return candidate

    def _overlay_path(self, report_id: str) -> Path:
        return self.overlay_dir / f"{report_id}.json"

    def _matching_overlay(self, report: dict) -> dict | None:
        path = self._overlay_path(report["run_id"])
        if not path.is_file():
            return None
        overlay = self._read_json(path, "legacy review overlay")
        if overlay.get("archive") != report.get("archive"):
            return None
        return overlay

    def _merge_overlay(self, report: dict) -> dict:
        path = self._overlay_path(report["run_id"])
        if not path.is_file():
            return report
        overlay = self._read_json(path, "legacy review overlay")
        if overlay.get("archive") != report.get("archive"):
            report["capabilities"]["review_overlay_stale"] = True
            return report
        for result_index, targets in overlay.get("reviews", {}).items():
            try:
                result = report["results"][int(result_index)]
            except (ValueError, IndexError):
                continue
            for target, review in targets.items():
                if target in result.get("human_review", {}) and isinstance(review, dict):
                    result["human_review"][target] = review
        report["human_review_status"] = self._review_status(report["results"])
        return report

    def _write_overlay(self, report_id: str, overlay: dict) -> None:
        path = self._overlay_path(report_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(overlay, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)

    @staticmethod
    def _read_json(path: Path, label: str) -> dict:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise LegacyArchiveError(f"{label} is missing: {path.name}") from exc
        except (OSError, json.JSONDecodeError) as exc:
            raise LegacyArchiveError(f"{label} is unreadable: {path.name}") from exc
        if not isinstance(value, dict):
            raise LegacyArchiveError(f"{label} must be a JSON object")
        return value
