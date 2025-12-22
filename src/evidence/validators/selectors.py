"""Shared selection helpers for validation (Milestone 7)."""

from __future__ import annotations

from typing import List, Sequence

from schemas.internal.evidence import FusedEvidenceCandidate


def select_passed_candidates(
    candidates: Sequence[FusedEvidenceCandidate],
    *,
    min_relevance_confidence: float = 0.6,
) -> List[FusedEvidenceCandidate]:
    """Return candidates that passed existence + relevance constraints."""
    selected: List[FusedEvidenceCandidate] = []
    for candidate in candidates:
        if candidate.existence is not None and candidate.existence.label != "pass":
            continue
        if candidate.relevance is None:
            continue
        if candidate.relevance.label != "relevant":
            continue
        if (candidate.relevance.confidence or 0.0) < min_relevance_confidence:
            continue
        selected.append(candidate)
    return selected


__all__ = ["select_passed_candidates"]

