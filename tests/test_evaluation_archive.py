import json
import hashlib
import shutil
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from classroom_simulator.evaluation_archive import (
    LegacyArchiveError,
    LegacyEvaluationArchive,
)
from classroom_simulator.evaluation_jobs import (
    EvaluationResultNotFoundError,
    InvalidReviewError,
)


PROJECT_DIR = Path(__file__).resolve().parents[1]


class LegacyEvaluationArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = TemporaryDirectory()
        self.overlay_dir = Path(self.temp_dir.name) / "overlays"
        self.archive = LegacyEvaluationArchive(PROJECT_DIR, self.overlay_dir)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_lists_only_four_approved_reports_newest_first(self):
        reports = self.archive.list_reports()

        self.assertEqual([report["run_id"] for report in reports], [
            "legacy-baseline-7b-v4-2",
            "legacy-baseline-3b-v4-2",
            "legacy-full-classroom-v4-2",
            "legacy-holdout-v1-3b-v4-2",
        ])
        self.assertTrue(all(report["legacy"] for report in reports))
        self.assertTrue(all("results" not in report for report in reports))

    def test_single_turn_report_is_enriched_from_versioned_scenario_catalog(self):
        report = self.archive.get_report("legacy-holdout-v1-3b-v4-2")
        result = report["results"][0]

        self.assertEqual(report["report_type"], "single_turn")
        self.assertEqual(report["evaluator_version"], "2.0")
        self.assertTrue(report["capabilities"]["scenario_evidence"])
        self.assertFalse(report["capabilities"]["raw_response"])
        self.assertEqual(
            result["teacher_message"],
            "小安，同樣大小的木塊和金屬塊拿起來不同，你還想追問什麼？",
        )
        self.assertEqual(result["expected_markers"], ["？", "嗎", "為什麼"])
        self.assertIsNone(result["raw_response"])
        self.assertEqual(set(result["human_review"]), {"delivered"})

    def test_full_classroom_turns_are_normalized_as_results(self):
        report = self.archive.get_report("legacy-full-classroom-v4-2")

        self.assertEqual(report["report_type"], "full_classroom")
        self.assertEqual(len(report["results"]), 10)
        self.assertEqual(report["results"][0]["result_index"], 0)
        self.assertEqual(
            report["results"][0]["teacher_message"],
            "小安，密度是什麼？你想到生活中的例子嗎？",
        )
        self.assertIn("delivered", report["results"][0]["human_review"])
        self.assertFalse(report["capabilities"]["raw_response"])
        self.assertEqual(report["summary"]["total_runs"], 10)
        self.assertEqual(report["summary"]["passed_runs"], 10)
        self.assertEqual(report["summary"]["pass_rate"], 1.0)

    def test_manifest_paths_cannot_escape_archive_directory(self):
        with TemporaryDirectory() as directory:
            project_dir = Path(directory)
            archive_dir = project_dir / "docs" / "evaluations"
            archive_dir.mkdir(parents=True)
            (archive_dir / "observatory-manifest.json").write_text(
                json.dumps(
                    {
                        "manifest_version": "1.0",
                        "reports": [
                            {
                                "id": "escape",
                                "title": "escape",
                                "path": "../outside.json",
                                "adapter": "single_turn_v2_1",
                                "expected_evaluator_version": "2.1",
                                "expected_suite": "baseline",
                                "scenario_catalog": "legacy-scenarios-evaluator-2.1.json",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaises(LegacyArchiveError):
                LegacyEvaluationArchive(project_dir, Path(directory) / "overlays").list_reports()

    def make_holdout_project(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        project_dir = Path(directory.name)
        archive_dir = project_dir / "docs" / "evaluations"
        results_dir = archive_dir / "results"
        results_dir.mkdir(parents=True)
        source_archive = PROJECT_DIR / "docs" / "evaluations"
        report_name = "2026-11-10-qwen2.5-3b-density-holdout-v1.json"
        shutil.copy2(source_archive / "results" / report_name, results_dir / report_name)
        shutil.copy2(
            source_archive / "legacy-scenarios-evaluator-2.1.json",
            archive_dir / "legacy-scenarios-evaluator-2.1.json",
        )
        (archive_dir / "observatory-manifest.json").write_text(
            json.dumps(
                {
                    "manifest_version": "1.0",
                    "reports": [
                        {
                            "id": "legacy-holdout",
                            "title": "holdout",
                            "path": f"results/{report_name}",
                            "adapter": "single_turn_v2_1",
                            "expected_evaluator_version": "2.0",
                            "expected_suite": "holdout",
                            "scenario_catalog": "legacy-scenarios-evaluator-2.1.json",
                            "used_holdout": True,
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        return project_dir, results_dir / report_name, project_dir / "overlays"

    def test_unknown_scenario_and_evaluator_mismatch_are_rejected(self):
        project_dir, report_path, overlay_dir = self.make_holdout_project()
        report = json.loads(report_path.read_text(encoding="utf-8"))
        report["results"][0]["scenario_id"] = "unknown-scenario"
        report_path.write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")

        with self.assertRaises(LegacyArchiveError):
            LegacyEvaluationArchive(project_dir, overlay_dir).get_report("legacy-holdout")

        report["results"][0]["scenario_id"] = "holdout-active-compares-materials"
        report["evaluator_version"] = "9.9"
        report_path.write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
        with self.assertRaises(LegacyArchiveError):
            LegacyEvaluationArchive(project_dir, overlay_dir).get_report("legacy-holdout")

    def test_missing_and_malformed_archive_reports_are_isolated_errors(self):
        project_dir, report_path, overlay_dir = self.make_holdout_project()
        report_path.unlink()
        with self.assertRaises(LegacyArchiveError):
            LegacyEvaluationArchive(project_dir, overlay_dir).get_report("legacy-holdout")

        report_path.write_text("{not json", encoding="utf-8")
        with self.assertRaises(LegacyArchiveError):
            LegacyEvaluationArchive(project_dir, overlay_dir).get_report("legacy-holdout")

    def test_review_overlay_persists_without_modifying_archive(self):
        project_dir, report_path, overlay_dir = self.make_holdout_project()
        archive_hash = hashlib.sha256(report_path.read_bytes()).hexdigest()
        archive = LegacyEvaluationArchive(project_dir, overlay_dir)
        judgments = {
            "directly_answers_teacher_request": "yes",
            "role_consistency": "no",
            "student_realism": "uncertain",
            "notes": "人工覆核完成",
        }

        updated = archive.update_review(
            "legacy-holdout", 0, "delivered", judgments, complete=True
        )

        self.assertEqual(
            updated["results"][0]["human_review"]["delivered"]["status"],
            "completed",
        )
        self.assertEqual(updated["human_review_status"]["targets"]["completed"], 1)
        self.assertEqual(hashlib.sha256(report_path.read_bytes()).hexdigest(), archive_hash)
        reloaded = LegacyEvaluationArchive(project_dir, overlay_dir).get_report("legacy-holdout")
        self.assertEqual(
            reloaded["results"][0]["human_review"]["delivered"]["notes"],
            "人工覆核完成",
        )

    def test_changed_archive_hash_does_not_silently_apply_old_overlay(self):
        project_dir, report_path, overlay_dir = self.make_holdout_project()
        archive = LegacyEvaluationArchive(project_dir, overlay_dir)
        archive.update_review(
            "legacy-holdout",
            0,
            "delivered",
            {"notes": "舊檔案的判讀"},
            complete=False,
        )
        report_path.write_text(report_path.read_text(encoding="utf-8") + "\n", encoding="utf-8")

        reloaded = LegacyEvaluationArchive(project_dir, overlay_dir).get_report("legacy-holdout")

        self.assertEqual(reloaded["results"][0]["human_review"]["delivered"]["notes"], "")
        self.assertTrue(reloaded["capabilities"]["review_overlay_stale"])

    def test_unavailable_target_and_result_index_are_rejected(self):
        project_dir, _, overlay_dir = self.make_holdout_project()
        archive = LegacyEvaluationArchive(project_dir, overlay_dir)

        with self.assertRaises(InvalidReviewError):
            archive.update_review("legacy-holdout", 0, "raw_model", {}, complete=False)
        with self.assertRaises(EvaluationResultNotFoundError):
            archive.update_review("legacy-holdout", 999, "delivered", {}, complete=False)


if __name__ == "__main__":
    unittest.main()
