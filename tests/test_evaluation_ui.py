import re
import shutil
import subprocess
import unittest
from html.parser import HTMLParser
from pathlib import Path


STATIC_DIR = Path(__file__).resolve().parents[1] / "classroom_simulator" / "static"


class DocumentContractParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.by_id = {}
        self.labels_for = set()
        self.links = set()
        self.scripts = set()
        self.stylesheets = set()
        self.inputs_by_name = {}

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        element_id = attributes.get("id")
        if element_id:
            self.by_id[element_id] = (tag, attributes)
        if tag == "label" and attributes.get("for"):
            self.labels_for.add(attributes["for"])
        if tag == "a" and attributes.get("href"):
            self.links.add(attributes["href"])
        if tag == "script" and attributes.get("src"):
            self.scripts.add(attributes["src"])
        if tag == "link" and attributes.get("rel") == "stylesheet":
            self.stylesheets.add(attributes.get("href"))
        if tag == "input" and attributes.get("name"):
            self.inputs_by_name.setdefault(attributes["name"], []).append(attributes)


class EvaluationObservatoryUiTests(unittest.TestCase):
    def setUp(self):
        self.html_path = STATIC_DIR / "evaluation.html"
        self.css_path = STATIC_DIR / "evaluation.css"
        self.js_path = STATIC_DIR / "evaluation.js"
        self.html = self.html_path.read_text(encoding="utf-8")
        self.parser = DocumentContractParser()
        self.parser.feed(self.html)

    def test_page_loads_its_assets_and_both_pages_link_to_each_other(self):
        self.assertTrue(self.css_path.is_file())
        self.assertTrue(self.js_path.is_file())
        self.assertIn("/static/evaluation.css", self.parser.stylesheets)
        self.assertIn("/static/evaluation.js", self.parser.scripts)
        self.assertIn("/", self.parser.links)

        classroom = DocumentContractParser()
        classroom.feed((STATIC_DIR / "index.html").read_text(encoding="utf-8"))
        self.assertIn("/evaluations", classroom.links)

    def test_workspace_has_accessible_native_controls_and_evidence_regions(self):
        expected = {
            "evaluation-provider": "select",
            "evaluation-suite": "select",
            "evaluation-model": "select",
            "evaluation-repeats": "input",
            "start-evaluation": "button",
            "run-history": "ol",
            "source-filter": "select",
            "hard-pass-filter": "select",
            "role-filter": "select",
            "review-filter": "select",
            "case-list": "ol",
            "case-detail": "section",
            "review-target": "select",
            "review-notes": "textarea",
            "save-review-draft": "button",
            "complete-review": "button",
        }
        for element_id, expected_tag in expected.items():
            with self.subTest(element_id=element_id):
                self.assertIn(element_id, self.parser.by_id)
                self.assertEqual(self.parser.by_id[element_id][0], expected_tag)

        labeled_controls = {
            "evaluation-provider",
            "evaluation-suite",
            "evaluation-model",
            "evaluation-repeats",
            "source-filter",
            "hard-pass-filter",
            "role-filter",
            "review-filter",
            "review-target",
            "review-notes",
        }
        self.assertTrue(labeled_controls.issubset(self.parser.labels_for))

        for name in (
            "directly_answers_teacher_request",
            "role_consistency",
            "student_realism",
        ):
            with self.subTest(review_field=name):
                options = self.parser.inputs_by_name.get(name, [])
                self.assertEqual({item.get("value") for item in options}, {"yes", "no", "uncertain"})
                self.assertTrue(all(item.get("type") == "radio" for item in options))

    def test_research_warnings_and_score_wording_preserve_data_meaning(self):
        visible_text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", self.html))
        self.assertIn("評測與課堂共用本機 Ollama", visible_text)
        self.assertIn("holdout v1 已使用", visible_text)
        self.assertIn("硬性規則通過率", visible_text)
        self.assertNotIn("模型準確率", visible_text)
        self.assertNotIn("學生真實度分數", visible_text)

    def test_layout_has_desktop_workspace_and_mobile_stacking(self):
        css = self.css_path.read_text(encoding="utf-8")
        self.assertRegex(css, r"\.observatory-workspace\s*\{[^}]*grid-template-columns")
        self.assertRegex(css, r"@media\s*\([^)]*max-width[^)]*\)")
        self.assertRegex(css, r"@media[\s\S]*\.observatory-workspace\s*\{[^}]*grid-template-columns:\s*1fr")

    def test_javascript_is_valid_and_connects_to_evaluation_endpoints(self):
        javascript = self.js_path.read_text(encoding="utf-8")
        self.assertIn("/api/models", javascript)
        self.assertIn("/api/evaluations", javascript)
        self.assertIn("queued", javascript)
        self.assertIn("running", javascript)
        self.assertIn("beforeunload", javascript)

        node = shutil.which("node")
        if node is None:
            self.skipTest("Node.js is unavailable for syntax validation")
        completed = subprocess.run(
            [node, "--check", str(self.js_path)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)


if __name__ == "__main__":
    unittest.main()
