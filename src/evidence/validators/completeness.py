"""Completeness reporting for validated evidence (Milestone 7)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Mapping, Sequence

from schemas.internal.evidence import CompletenessItem, FusedEvidenceCandidate
from schemas.internal.rob2 import QuestionSet


@dataclass(frozen=True)
class CompletenessValidatorConfig:
    enforce: bool = False
    required_question_ids: set[str] | None = None
    min_passed_per_question: int = 1


def compute_completeness(
    question_set: QuestionSet,
    validated_candidates_by_q: Mapping[str, Sequence[FusedEvidenceCandidate]],
    *,
    config: CompletenessValidatorConfig | None = None,
) -> tuple[bool, List[CompletenessItem], List[str]]:
    """Compute completeness items and pass/fail based on required questions."""
    cfg = config or CompletenessValidatorConfig()
    if cfg.min_passed_per_question < 1:
        raise ValueError("min_passed_per_question must be >= 1")

    if cfg.required_question_ids is None:
        required_ids: set[str] = set()
        if cfg.enforce:
            required_ids = {q.question_id for q in question_set.questions}
    else:
        required_ids = set(cfg.required_question_ids)

    failed: List[str] = []
    items: List[CompletenessItem] = []
    for question in question_set.questions:
        count = len(validated_candidates_by_q.get(question.question_id) or [])
        required = question.question_id in required_ids
        status = "satisfied" if count >= cfg.min_passed_per_question else "missing"
        items.append(
            CompletenessItem(
                question_id=question.question_id,
                required=required,
                passed_count=count,
                status=status,
            )
        )
        if required and status == "missing":
            failed.append(question.question_id)

    passed = len(failed) == 0
    if not cfg.enforce and cfg.required_question_ids is None:
        passed = True

    return passed, items, failed


__all__ = ["CompletenessValidatorConfig", "compute_completeness"]

