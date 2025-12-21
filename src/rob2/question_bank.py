"""Load the ROB2 question bank from YAML."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

from schemas.internal.rob2 import QuestionSet

DEFAULT_QUESTION_BANK = Path(__file__).resolve().parent / "rob2_questions.yaml"


def load_question_bank(path: Path | str | None = None) -> QuestionSet:
    """Load and validate the ROB2 question bank from YAML."""
    resolved = Path(path) if path else DEFAULT_QUESTION_BANK
    if not resolved.exists():
        raise FileNotFoundError(f"Question bank not found: {resolved}")

    raw = yaml.safe_load(resolved.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Question bank must be a YAML mapping")

    questions = raw.get("questions")
    if not isinstance(questions, list):
        raise ValueError("Question bank must include a questions list")

    for index, item in enumerate(questions, start=1):
        if isinstance(item, dict) and "order" not in item:
            item["order"] = index

    return QuestionSet.model_validate(raw)


@lru_cache(maxsize=2)
def get_question_bank(path: str | None = None) -> QuestionSet:
    """Return cached question bank for reuse in the planner."""
    resolved: Path | None = Path(path) if path else None
    return load_question_bank(resolved)


__all__ = ["DEFAULT_QUESTION_BANK", "get_question_bank", "load_question_bank"]
