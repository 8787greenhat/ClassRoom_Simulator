from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from typing import Iterable

from .llm import LLMProvider, MockProvider, OllamaProvider
from .models import StudentState
from .roles import PROFILES_BY_ID


@dataclass(frozen=True)
class EvaluationScenario:
    id: str
    role_id: str
    teacher_message: str
    misconception_strength: int = 0
    expected_markers: tuple[str, ...] = ()
    forbidden_markers: tuple[str, ...] = ("身為 AI", "作為 AI", "你的教學很好")


SCENARIOS: tuple[EvaluationScenario, ...] = (
    EvaluationScenario(
        id="active-asks-extension",
        role_id="active",
        teacher_message="密度是質量除以體積。小安，你想到什麼問題？",
        expected_markers=("？", "嗎", "為什麼"),
    ),
    EvaluationScenario(
        id="typical-exposes-uncertainty",
        role_id="typical",
        teacher_message="密度公式說完了，小明你懂了嗎？",
        expected_markers=("不太", "不確定", "卡住", "疑惑", "嗎", "呢"),
    ),
    EvaluationScenario(
        id="misconception-resists-praise",
        role_id="misconception",
        teacher_message="小哲，你回答得很好，所以你同意重量不能決定密度了吧？",
        misconception_strength=3,
        expected_markers=("可是", "為什麼", "還是", "不懂", "不相信"),
    ),
    EvaluationScenario(
        id="reserved-is-cautious",
        role_id="reserved",
        teacher_message="小晴，同一材料切小塊後密度會改變嗎？",
        misconception_strength=1,
        expected_markers=("不太", "不確定", "嗎", "……"),
    ),
    EvaluationScenario(
        id="distracted-requests-context",
        role_id="distracted",
        teacher_message="小宇，你有在聽嗎？請回答剛才的問題。",
        expected_markers=("剛剛", "沒跟上", "哪", "什麼"),
    ),
)


def score_response(scenario: EvaluationScenario, response: str) -> dict:
    """Score observable constraints without claiming semantic correctness."""
    expected_hit = any(marker in response for marker in scenario.expected_markers)
    forbidden_hits = [marker for marker in scenario.forbidden_markers if marker in response]
    length_ok = 0 < len(response) <= 45
    checks = {
        "non_empty_and_within_45_chars": length_ok,
        "has_expected_role_marker": expected_hit,
        "has_no_forbidden_marker": not forbidden_hits,
    }
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "forbidden_hits": forbidden_hits,
        "response_length": len(response),
    }


def evaluate_provider(
    provider: LLMProvider,
    scenarios: Iterable[EvaluationScenario] = SCENARIOS,
    repeats: int = 1,
) -> dict:
    if repeats < 1:
        raise ValueError("repeats must be at least 1")

    scenario_list = tuple(scenarios)
    results = []
    for scenario in scenario_list:
        profile = PROFILES_BY_ID[scenario.role_id]
        for run in range(1, repeats + 1):
            state = StudentState(
                role_id=scenario.role_id,
                misconception_strength=scenario.misconception_strength,
            )
            reply = provider.reply(
                profile,
                state,
                scenario.teacher_message,
                "國中自然科：密度",
                "理解密度是質量與體積的比值，並修正常見迷思",
            )
            score = score_response(scenario, reply.response)
            results.append(
                {
                    "scenario_id": scenario.id,
                    "role_id": scenario.role_id,
                    "run": run,
                    "provider": reply.provider,
                    "response": reply.response,
                    **score,
                }
            )

    passed = sum(item["passed"] for item in results)
    return {
        "provider": provider.name,
        "scenario_count": len(scenario_list),
        "repeats": repeats,
        "total_runs": len(results),
        "passed_runs": passed,
        "pass_rate": passed / len(results) if results else 0.0,
        "results": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate student-role consistency.")
    parser.add_argument("--provider", choices=("mock", "ollama"), default="mock")
    parser.add_argument("--repeats", type=int, default=1)
    args = parser.parse_args()

    provider: LLMProvider = MockProvider() if args.provider == "mock" else OllamaProvider()
    report = evaluate_provider(provider, repeats=args.repeats)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
