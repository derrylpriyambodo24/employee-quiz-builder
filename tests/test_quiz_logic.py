import json
import random
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from quiz_logic import extract_json, generate_quiz, shuffle_options, validate_quiz


def make_quiz(n=2):
    return {
        "topic": "t",
        "difficulty": "easy",
        "questions": [
            {
                "id": i,
                "question": f"Q{i}?",
                "options": {"A": "a", "B": "b", "C": "c", "D": "d"},
                "correct": "A",
                "explanation": "because",
            }
            for i in range(1, n + 1)
        ],
    }


def test_extract_json_strips_fences():
    raw = "```json\n" + json.dumps(make_quiz()) + "\n```"
    assert extract_json(raw)["topic"] == "t"


def test_validate_rejects_bad_option_keys():
    quiz = make_quiz()
    del quiz["questions"][0]["options"]["D"]
    with pytest.raises(ValueError):
        validate_quiz(quiz)


def test_validate_rejects_wrong_count():
    with pytest.raises(ValueError):
        validate_quiz(make_quiz(2), expected_n=3)


def test_shuffle_keeps_correct_answer_text():
    quiz = shuffle_options(make_quiz(20), random.Random(1))
    for q in quiz["questions"]:
        assert q["options"][q["correct"]] == "a"
    assert len({q["correct"] for q in quiz["questions"]}) > 1


def test_retry_after_invalid_json():
    calls = []

    def fake_llm(system, messages):
        calls.append(len(messages))
        return "not json" if len(calls) == 1 else json.dumps(make_quiz(2))

    quiz = generate_quiz("topic", 2, "easy", "English", llm=fake_llm)
    assert calls == [1, 3]
    assert len(quiz["questions"]) == 2


def test_gives_up_after_second_failure():
    with pytest.raises(Exception):
        generate_quiz("topic", 2, "easy", "English", llm=lambda s, m: "still not json")
