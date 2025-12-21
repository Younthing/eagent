"""Domain question planner node."""

from __future__ import annotations

from rob2.question_bank import get_question_bank


def planner_node(state: dict) -> dict:
    """Return the standardized ROB2 question set."""
    question_set = get_question_bank()
    return {"question_set": question_set.model_dump()}


__all__ = ["planner_node"]
