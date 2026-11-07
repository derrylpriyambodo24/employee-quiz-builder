"""Core logic: prompt loading, LLM call, JSON parsing/validation, option shuffling."""
import json
import os
import random
import re
from pathlib import Path

PROMPT_DIR = Path(__file__).parent / "prompts"
LETTERS = ["A", "B", "C", "D"]


def load_prompt(name: str) -> str:
    return (PROMPT_DIR / name).read_text(encoding="utf-8")


def extract_json(text: str) -> dict:
    """Strip markdown fences / stray text and parse the first JSON object."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("No JSON object found in the response")
    return json.loads(text[start : end + 1])


def validate_quiz(data: dict, expected_n: int | None = None) -> None:
    """Raise ValueError with a readable message if the quiz breaks the schema."""
    if not isinstance(data, dict) or not isinstance(data.get("questions"), list):
        raise ValueError('Top-level object must contain a "questions" list')
    questions = data["questions"]
    if not questions:
        raise ValueError("The questions list is empty")
    if expected_n is not None and len(questions) != expected_n:
        raise ValueError(f"Expected {expected_n} questions but got {len(questions)}")
    for i, q in enumerate(questions, start=1):
        if not isinstance(q, dict):
            raise ValueError(f"Question {i} is not an object")
        if not str(q.get("question", "")).strip():
            raise ValueError(f"Question {i} has no question text")
        opts = q.get("options")
        if not isinstance(opts, dict) or sorted(opts.keys()) != LETTERS:
            raise ValueError(f"Question {i} must have exactly options A, B, C, D")
        if any(not str(v).strip() for v in opts.values()):
            raise ValueError(f"Question {i} has an empty option")
        if q.get("correct") not in LETTERS:
            raise ValueError(f'Question {i} has an invalid "correct" value')
        if not str(q.get("explanation", "")).strip():
            raise ValueError(f"Question {i} has no explanation")


def shuffle_options(quiz: dict, rng: random.Random | None = None) -> dict:
    """Randomize option order in code (guards against answer-position bias)."""
    rng = rng or random.Random()
    for q in quiz["questions"]:
        correct_text = q["options"][q["correct"]]
        texts = [q["options"][letter] for letter in LETTERS]
        rng.shuffle(texts)
        q["options"] = dict(zip(LETTERS, texts))
        q["correct"] = LETTERS[texts.index(correct_text)]
    return quiz


RISKY_PATTERNS = {
    "mentions a specific year": re.compile(r"\b(19|20)\d{2}\b"),
    "mentions a percentage": re.compile(r"\d+(\.\d+)?\s?%|\bpercent\b", re.IGNORECASE),
    "cites a source or news-style claim": re.compile(
        r"\b(according to|survey|BPS|announced|upcoming|slated|projected|is expected to|are expected to)\b",
        re.IGNORECASE,
    ),
}
MAX_RETRIES = 2


def flag_risky(quiz: dict) -> dict[int, list[str]]:
    """Find questions with specific claims the model cannot verify (years, %, sources, news)."""
    flags: dict[int, list[str]] = {}
    for q in quiz["questions"]:
        text = " ".join([q["question"], q["explanation"], *q["options"].values()])
        reasons = [name for name, pattern in RISKY_PATTERNS.items() if pattern.search(text)]
        if reasons:
            flags[q["id"]] = reasons
    return flags


def describe_flags(flags: dict[int, list[str]]) -> str:
    return "; ".join(f"question {qid} ({', '.join(r)})" for qid, r in flags.items())


def call_llm(system: str, messages: list[dict]) -> str:
    """Call any OpenAI-compatible chat API (Groq, Gemini, OpenRouter, ...).

    Configure with LLM_API_KEY, LLM_BASE_URL and LLM_MODEL in .env.
    Swap this function if you want a provider-specific SDK instead.
    """
    from openai import APIStatusError, OpenAI

    api_key = os.getenv("LLM_API_KEY")
    if not api_key:
        raise RuntimeError("LLM_API_KEY is missing. Copy .env.example to .env and add your key.")
    client = OpenAI(
        api_key=api_key,
        base_url=os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1"),
    )
    try:
        response = client.chat.completions.create(
            model=os.getenv("LLM_MODEL", "openai/gpt-oss-120b"),
            messages=[{"role": "system", "content": system}] + messages,
            temperature=0.4,
        )
    except APIStatusError as err:
        # Show the provider's full error body (the SDK message alone is often just "Error code: 400")
        raise RuntimeError(f"API error {err.status_code}: {err.response.text}") from err
    return response.choices[0].message.content or ""


def generate_quiz(topic: str, n: int, difficulty: str, language: str, llm=call_llm) -> dict:
    """Generate a validated quiz.

    Retries (up to MAX_RETRIES) when the JSON is invalid or when questions contain claims the
    model cannot verify. If risky claims remain, they are returned in quiz["warnings"].
    """
    system = load_prompt("system_prompt.txt")
    user = load_prompt("user_prompt.txt").format(
        n=n, topic=topic, difficulty=difficulty, language=language
    )
    messages = [{"role": "user", "content": user}]
    best, best_flags, last_err = None, {}, None
    for attempt in range(MAX_RETRIES + 1):
        raw = llm(system, messages)
        try:
            quiz = extract_json(raw)
            validate_quiz(quiz, expected_n=n)
            flags = flag_risky(quiz)
            best, best_flags, last_err = quiz, flags, None
            if not flags:
                break
            feedback = load_prompt("claims_prompt.txt").format(details=describe_flags(flags))
        except (ValueError, json.JSONDecodeError) as err:
            last_err = err
            feedback = load_prompt("repair_prompt.txt").format(error_message=str(err))
        if attempt < MAX_RETRIES:
            messages += [
                {"role": "assistant", "content": raw},
                {"role": "user", "content": feedback},
            ]
    if best is None:
        raise last_err
    shuffle_options(best)
    if best_flags:
        best["warnings"] = [f"Q{qid}: {', '.join(r)}" for qid, r in best_flags.items()]
    return best
