"""Rank fusion utilities (Milestone 4)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple


@dataclass(frozen=True)
class RrfHit:
    doc_index: int
    rrf_score: float
    best_rank: int
    query_ranks: Dict[str, int]
    best_query: str
    best_engine_score: float


def rrf_fuse(
    rankings: Dict[str, List[Tuple[int, float]]],
    *,
    k: int = 60,
) -> List[RrfHit]:
    """Fuse multiple ranked lists using reciprocal rank fusion (RRF)."""
    fused: Dict[int, float] = {}
    query_ranks: Dict[int, Dict[str, int]] = {}
    best_rank: Dict[int, int] = {}
    best_engine_score: Dict[int, float] = {}
    best_query: Dict[int, str] = {}

    for query, hits in rankings.items():
        for rank, (doc_index, engine_score) in enumerate(hits, start=1):
            fused[doc_index] = fused.get(doc_index, 0.0) + 1.0 / (k + rank)
            query_ranks.setdefault(doc_index, {})[query] = rank
            best_rank[doc_index] = min(best_rank.get(doc_index, rank), rank)
            prev_best = best_engine_score.get(doc_index)
            if prev_best is None or engine_score > prev_best:
                best_engine_score[doc_index] = engine_score
                best_query[doc_index] = query

    results: List[RrfHit] = []
    for doc_index, rrf_score in fused.items():
        ranks = query_ranks.get(doc_index, {})
        results.append(
            RrfHit(
                doc_index=doc_index,
                rrf_score=rrf_score,
                best_rank=best_rank.get(doc_index, 10**9),
                query_ranks=ranks,
                best_query=best_query.get(doc_index, ""),
                best_engine_score=best_engine_score.get(doc_index, 0.0),
            )
        )

    results.sort(
        key=lambda hit: (
            -hit.rrf_score,
            hit.best_rank,
            -hit.best_engine_score,
            hit.doc_index,
        )
    )
    return results


def truncate_rankings(
    rankings: Dict[str, List[Tuple[int, float]]],
    *,
    top_n: int,
) -> Dict[str, List[Tuple[int, float]]]:
    """Keep only top_n hits per query ranking list."""
    if top_n < 1:
        raise ValueError("top_n must be >= 1")
    return {query: hits[:top_n] for query, hits in rankings.items()}


__all__ = ["RrfHit", "rrf_fuse", "truncate_rankings"]
