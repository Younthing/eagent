"""Section title normalization and scoring for structure-aware retrieval."""

from __future__ import annotations

import re
from typing import List, Sequence, Tuple

_NON_WORD = re.compile(r"[^a-z0-9]+")
_WS = re.compile(r"\s+")


def normalize_for_match(text: str) -> str:
    lowered = text.casefold()
    lowered = lowered.replace("-", " ").replace("–", " ").replace("—", " ")
    lowered = _NON_WORD.sub(" ", lowered)
    return _WS.sub(" ", lowered).strip()


def score_section_title(title: str, priors: Sequence[str]) -> Tuple[int, List[str]]:
    """Return a section score and matched priors (higher score = higher priority)."""
    if not priors:
        return 0, []

    normalized_title = normalize_for_match(title)
    if not normalized_title:
        return 0, []

    matched: List[str] = []
    score = 0
    for index, prior in enumerate(priors):
        needle = normalize_for_match(prior)
        if not needle:
            continue
        if needle in normalized_title:
            matched.append(prior)
            score = max(score, len(priors) - index)
    return score, matched


__all__ = ["normalize_for_match", "score_section_title"]

