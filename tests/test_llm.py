import json
import unittest
from unittest.mock import patch

from classroom_simulator.llm import (
    MockProvider,
    OllamaProvider,
    enforce_response_length,
    normalize_student_response,
)
from classroom_simulator.models import StudentState
from classroom_simulator.roles import PROFILES_BY_ID


class FakeHttpResponse:
    def __init__(self, payload: dict):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self) -> bytes:
        return json.dumps(self.payload, ensure_ascii=False).encode("utf-8")


class StudentResponseValidationTests(unittest.TestCase):
    def test_mock_reply_preserves_same_raw_and_final_response(self):
        reply = MockProvider().reply(
            PROFILES_BY_ID["active"],
            StudentState(role_id="active"),
            "密度是質量除以體積。小安，你想到什麼問題？",
            "國中自然科：密度",
            "理解密度",
        )

        self.assertEqual(reply.raw_response, reply.response)

    def test_guarded_ollama_reply_preserves_text_before_guard(self):
        raw_text = "你說得對，重量和密度沒有直接關係。"
        response = FakeHttpResponse(
            {
                "message": {
                    "content": json.dumps(
                        {"response": raw_text, "emotion": "confident"},
                        ensure_ascii=False,
                    )
                }
            }
        )
        with patch("classroom_simulator.llm.urllib.request.urlopen", return_value=response):
            reply = OllamaProvider().reply(
                PROFILES_BY_ID["misconception"],
                StudentState(role_id="misconception", misconception_strength=3),
                "小哲，你回答得很好，所以你同意重量不能決定密度了吧？",
                "國中自然科：密度",
                "理解密度",
            )

        self.assertTrue(reply.guarded)
        self.assertEqual(reply.raw_response, raw_text)
        self.assertNotEqual(reply.response, raw_text)

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
