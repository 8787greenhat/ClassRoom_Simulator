import unittest

from classroom_simulator.llm import normalize_student_response


class StudentResponseValidationTests(unittest.TestCase):
    def test_rejects_schema_placeholder(self):
        with self.assertRaises(ValueError):
            normalize_student_response("學生發言")

    def test_rejects_whitespace_only_response(self):
        with self.assertRaises(ValueError):
            normalize_student_response("  \n  ")

    def test_normalizes_multiline_response_to_one_utterance(self):
        response = normalize_student_response("第一句。\n第二句。")
        self.assertEqual(response, "第一句。 第二句。")


if __name__ == "__main__":
    unittest.main()
