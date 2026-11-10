import unittest

from classroom_simulator.llm import enforce_response_length, normalize_student_response


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

    def test_short_response_is_not_rewritten(self):
        response, guarded = enforce_response_length("我還不太確定，為什麼還要看體積？")

        self.assertEqual(response, "我還不太確定，為什麼還要看體積？")
        self.assertFalse(guarded)

    def test_long_response_is_shortened_and_marked(self):
        response, guarded = enforce_response_length("這是一段沒有句號而且明顯超過限制的學生回答" * 3)

        self.assertLessEqual(len(response), 45)
        self.assertTrue(response.endswith("…"))
        self.assertTrue(guarded)

    def test_long_response_prefers_complete_sentence(self):
        response, guarded = enforce_response_length(
            "我還是不太相信這個說法。後面繼續補充很多很多不必要的文字直到超過限制。"
            "這一段會繼續補上非常多沒有必要而且沒有句號的文字內容"
        )

        self.assertEqual(response, "我還是不太相信這個說法。後面繼續補充很多很多不必要的文字直到超過限制。")
        self.assertLessEqual(len(response), 45)
        self.assertTrue(guarded)


if __name__ == "__main__":
    unittest.main()
