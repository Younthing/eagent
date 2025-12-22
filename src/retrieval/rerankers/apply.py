"""Helpers to apply rerankers to retrieved EvidenceCandidates."""

from __future__ import annotations

from typing import List, Sequence

from retrieval.rerankers.contracts import Reranker
from schemas.internal.evidence import EvidenceCandidate


def apply_reranker(
    *,
    reranker: Reranker,
    query: str,
    candidates: Sequence[EvidenceCandidate],
    top_n: int,
    max_length: int,
    batch_size: int,
) -> List[EvidenceCandidate]:
    """Return candidates reordered by reranker score (top_n), keeping full list."""
    if top_n < 1:
        raise ValueError("top_n must be >= 1")
    if not candidates:
        return []

    head = list(candidates[:top_n])
    tail = list(candidates[top_n:])

    passages = [_format_passage(candidate) for candidate in head]
    result = reranker.rerank(
        query,
        passages,
        max_length=max_length,
        batch_size=batch_size,
    )
    if len(result.scores) != len(head):
        raise RuntimeError("Reranker score count mismatch.")
    if sorted(result.order) != list(range(len(head))):
        raise RuntimeError("Reranker order must be a permutation of indices.")

    reranked: List[EvidenceCandidate] = []
    for new_rank, old_index in enumerate(result.order, start=1):
        candidate = head[old_index]
        score = float(result.scores[old_index])
        reranked.append(
            candidate.model_copy(
                update={
                    "score": score,
                    "reranker": reranker.name,
                    "rerank_score": score,
                    "rerank_rank": new_rank,
                }
            )
        )

    offset = len(reranked)
    for index, candidate in enumerate(tail, start=1):
        reranked.append(
            candidate.model_copy(
                update={
                    "reranker": reranker.name,
                    "rerank_rank": offset + index,
                }
            )
        )

    return reranked


def _format_passage(candidate: EvidenceCandidate) -> str:
    title = (candidate.title or "").strip()
    text = (candidate.text or "").strip()
    if title:
        return f"{title}\n\n{text}".strip()
    return text


__all__ = ["apply_reranker"]

