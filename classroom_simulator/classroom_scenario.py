from __future__ import annotations

import argparse
import json
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from .db import Database
from .llm import (
    DENSITY_PROMPT_VERSION,
    INVALID_STUDENT_RESPONSES,
    LLMProvider,
    MockProvider,
    OllamaProvider,
    ResilientProvider,
)
from .evaluation import pending_human_review, response_source
from .service import ClassroomService


@dataclass(frozen=True)
class ClassroomTurn:
    id: str
    teacher_message: str
    expected_role_id: str
    expected_behavior_type: str = "on_task"
    expected_misconception_strength: int | None = None


FULL_CLASSROOM_TURNS: tuple[ClassroomTurn, ...] = (
    ClassroomTurn(
        id="active-opens-with-example",
        teacher_message="小安，密度是什麼？你想到生活中的例子嗎？",
        expected_role_id="active",
    ),
    ClassroomTurn(
        id="typical-exposes-confusion",
        teacher_message="小明，如果質量增加，密度就一定增加嗎？你哪裡不確定？",
        expected_role_id="typical",
    ),
    ClassroomTurn(
        id="misconception-states-belief",
        teacher_message="小哲，物體越重，密度就一定越大嗎？",
        expected_role_id="misconception",
        expected_misconception_strength=3,
    ),
    ClassroomTurn(
        id="reserved-answers-cautiously",
        teacher_message="小晴，同一材料切成小塊後，密度會改變嗎？",
        expected_role_id="reserved",
    ),
    ClassroomTurn(
        id="distracted-missed-context",
        teacher_message="小宇，你有在聽嗎？請回答剛才的問題。",
        expected_role_id="distracted",
        expected_behavior_type="distracted",
    ),
    ClassroomTurn(
        id="teacher-redirects-distracted",
        teacher_message="小宇，回到問題：質量相同時要怎麼比較密度？",
        expected_role_id="distracted",
        expected_behavior_type="redirected",
    ),
    ClassroomTurn(
        id="misconception-first-evidence",
        teacher_message="小哲，密度是質量除以體積，所以不能只看質量。請舉例再說一次，對不對？",
        expected_role_id="misconception",
        expected_misconception_strength=2,
    ),
    ClassroomTurn(
        id="misconception-second-evidence",
        teacher_message="小哲，再比較質量和體積的比值，所以密度不能只看重量。請用自己的話再說一次。",
        expected_role_id="misconception",
        expected_misconception_strength=1,
    ),
    ClassroomTurn(
        id="active-applies-concept",
        teacher_message="小安，如果兩個物體體積相同，要怎麼比較密度？",
        expected_role_id="active",
    ),
    ClassroomTurn(
        id="typical-closes-lesson",
        teacher_message="小明，最後請你說說看，為什麼不能只用重量判斷密度？",
        expected_role_id="typical",
    ),
)

AI_DISCLOSURE_MARKERS = ("身為 AI", "作為 AI", "語言模型")


def _student_state(snapshot: dict, role_id: str) -> dict:
    return next(student["state"] for student in snapshot["students"] if student["id"] == role_id)


def run_full_classroom(service: ClassroomService, provider: LLMProvider) -> dict:
    snapshot = service.create_session()
    session_id = snapshot["session"]["id"]
    turn_results = []

    for index, turn in enumerate(FULL_CLASSROOM_TURNS, start=1):
        snapshot = service.send_teacher_message(session_id, turn.teacher_message)
        event = snapshot["events"][-1]
        response = event["content"]
        metadata = event["metadata"]
        misconception_strength = _student_state(snapshot, "misconception")[
            "misconception_strength"
        ]
        checks = {
            "expected_speaker": event["speaker_id"] == turn.expected_role_id,
            "expected_behavior": metadata.get("behavior_type") == turn.expected_behavior_type,
            "within_45_chars": 0 < len(response) <= 45,
            "not_placeholder": response not in INVALID_STUDENT_RESPONSES,
            "single_line": "\n" not in response and "\r" not in response,
            "no_ai_disclosure": not any(marker in response for marker in AI_DISCLOSURE_MARKERS),
        }
        if turn.expected_misconception_strength is not None:
            checks["expected_misconception_strength"] = (
                misconception_strength == turn.expected_misconception_strength
            )

        turn_results.append(
            {
                "turn": index,
                **asdict(turn),
                "actual_role_id": event["speaker_id"],
                "response": response,
                "response_length": len(response),
                "emotion": metadata.get("emotion"),
                "provider": metadata.get("provider"),
                "behavior_type": metadata.get("behavior_type"),
                "guarded": metadata.get("guarded", False),
                "guard_reason": metadata.get("guard_reason"),
                "source_category": response_source(
                    str(metadata.get("provider")),
                    bool(metadata.get("guarded", False)),
                    fallback_possible=isinstance(provider, ResilientProvider),
                ),
                "misconception_strength": misconception_strength,
                "checks": checks,
                "passed": all(checks.values()),
                "human_review": pending_human_review(),
            }
        )

    snapshot = service.finish_session(session_id)
    participation = {
        student["id"]: student["state"]["participation_count"]
        for student in snapshot["students"]
    }
    final_misconception_strength = _student_state(snapshot, "misconception")[
        "misconception_strength"
    ]
    final_checks = {
        "session_finished": snapshot["session"]["status"] == "finished",
        "ten_teacher_student_turns": len(snapshot["events"]) == len(FULL_CLASSROOM_TURNS) * 2,
        "all_five_roles_participated": all(count > 0 for count in participation.values()),
        "misconception_reduced_gradually_to_one": final_misconception_strength == 1,
        "all_targeted_roles_selected": all(
            result["checks"]["expected_speaker"] for result in turn_results
        ),
    }
    passed_turns = sum(result["passed"] for result in turn_results)
    guarded_turns = sum(result["guarded"] for result in turn_results)
    provider_usage: dict[str, int] = {}
    source_usage: dict[str, int] = {}
    for result in turn_results:
        provider_name = result["provider"]
        provider_usage[provider_name] = provider_usage.get(provider_name, 0) + 1
        source_category = result["source_category"]
        source_usage[source_category] = source_usage.get(source_category, 0) + 1

    provider_config = {"name": provider.name}
    if isinstance(provider, OllamaProvider):
        provider_config.update(
            {"model": provider.model, "temperature": 0.65, "num_predict": 100}
        )
    elif isinstance(provider, ResilientProvider):
        provider_config.update(
            {
                "primary": provider.primary.name,
                "model": provider.primary.model,
                "fallback": provider.fallback.name,
                "temperature": 0.65,
                "num_predict": 100,
            }
        )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scenario_version": "full-classroom-density-v1",
        "prompt_version": DENSITY_PROMPT_VERSION,
        "provider_config": provider_config,
        "summary": {
            "total_turns": len(turn_results),
            "passed_turns": passed_turns,
            "turn_pass_rate": passed_turns / len(turn_results),
            "guarded_turns": guarded_turns,
            "provider_usage": provider_usage,
            "source_usage": source_usage,
            "human_review_status": {"pending": len(turn_results), "completed": 0},
            "participation": participation,
            "final_misconception_strength": final_misconception_strength,
            "final_checks": final_checks,
            "passed": all(final_checks.values()) and passed_turns == len(turn_results),
        },
        "turns": turn_results,
        "final_snapshot": snapshot,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the complete density classroom scenario.")
    parser.add_argument("--provider", choices=("mock", "ollama"), default="mock")
    parser.add_argument("--output", type=Path, help="Write the full JSON record to this path.")
    args = parser.parse_args()

    provider: LLMProvider
    if args.provider == "mock":
        provider = MockProvider()
    else:
        provider = ResilientProvider(primary=OllamaProvider(), fallback=MockProvider())
    with tempfile.TemporaryDirectory() as directory:
        service = ClassroomService(Database(Path(directory) / "classroom.db"), provider)
        report = run_full_classroom(service, provider)

    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
        print(
            json.dumps(
                {
                    "output": str(args.output),
                    **report["summary"],
                },
                ensure_ascii=False,
            )
        )
    else:
        print(rendered)


if __name__ == "__main__":
    main()
