"""Corpus filtering based on section priors (Milestone 5)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Sequence

from schemas.internal.documents import SectionSpan

from .section_prior import score_section_title


@dataclass(frozen=True)
class SectionFilterResult:
    indices: List[int]
    section_scores: Dict[int, int]
    matched_priors: Dict[int, List[str]]


def filter_spans_by_section_priors(
    spans: Sequence[SectionSpan],
    priors: Sequence[str],
) -> SectionFilterResult:
    """Return span indices that match section priors, preserving original order."""
    indices: List[int] = []
    scores: Dict[int, int] = {}
    matched: Dict[int, List[str]] = {}

    for idx, span in enumerate(spans):
        score, matched_priors = score_section_title(span.title, priors)
        if score <= 0:
            continue
        indices.append(idx)
        scores[idx] = score
        if matched_priors:
            matched[idx] = matched_priors

    return SectionFilterResult(indices=indices, section_scores=scores, matched_priors=matched)


__all__ = ["SectionFilterResult", "filter_spans_by_section_priors"]

