"""Evidence fusion across multiple locator engines (Milestone 6).

This module merges candidates from rule-based and retrieval engines into a single
ranked list per question_id, with explicit source attribution.
"""

from __future__ import annotations

from typing import Dict, List, Mapping, Sequence

from schemas.internal.evidence import (
    EvidenceCandidate,
    EvidenceSupport,
    FusedEvidenceCandidate,
    RelevanceVerdict,
)


def fuse_candidates_for_question(
    question_id: str,
    *,
    candidates_by_engine: Mapping[str, Sequence[EvidenceCandidate]],
    rrf_k: int = 60,
    engine_weights: Mapping[str, float] | None = None,
) -> List[FusedEvidenceCandidate]:
    """Fuse multi-engine candidates for a single question using rank-based RRF."""
    if rrf_k < 1:
        raise ValueError("rrf_k must be >= 1")

    weights = dict(engine_weights) if engine_weights else {}
    for engine, weight in weights.items():
        if weight < 0:
            raise ValueError(f"engine_weights[{engine!r}] must be >= 0")

    supports_by_pid: Dict[str, Dict[str, EvidenceSupport]] = {}
    best_candidate_by_pid: Dict[str, EvidenceCandidate] = {}
    best_rank_by_pid: Dict[str, int] = {}

    for engine, candidates in candidates_by_engine.items():
        for rank, candidate in enumerate(candidates, start=1):
            if candidate.question_id != question_id:
                continue
            pid = candidate.paragraph_id
            if not pid:
                continue

            support = EvidenceSupport(
                engine=engine,
                rank=rank,
                score=float(candidate.score),
                query=candidate.query,
            )
            support_map = supports_by_pid.setdefault(pid, {})
            existing = support_map.get(engine)
            if existing is None or rank < existing.rank:
                support_map[engine] = support

            prev_best = best_rank_by_pid.get(pid)
            if prev_best is None or rank < prev_best:
                best_rank_by_pid[pid] = rank
                best_candidate_by_pid[pid] = candidate

    fused_rows: List[tuple[str, float, int, int]] = []
    for pid, support_map in supports_by_pid.items():
        if not support_map:
            continue
        supports = list(support_map.values())
        support_count = len(supports)
        best_rank = min(s.rank for s in supports)
        fusion_score = 0.0
        for support in supports:
            weight = float(weights.get(support.engine, 1.0))
            fusion_score += weight * (1.0 / (rrf_k + support.rank))
        fused_rows.append((pid, fusion_score, support_count, best_rank))

    fused_rows.sort(
        key=lambda row: (
            -row[1],  # fusion_score
            -row[2],  # support_count
            row[3],  # best_rank
            row[0],  # paragraph_id
        )
    )

    fused: List[FusedEvidenceCandidate] = []
    for fusion_rank, (pid, fusion_score, support_count, _best_rank) in enumerate(
        fused_rows, start=1
    ):
        candidate = best_candidate_by_pid[pid]
        relevance = None
        if candidate.supporting_quote:
            relevance = RelevanceVerdict(
                label="relevant",
                confidence=1.0,
                supporting_quote=candidate.supporting_quote,
            )
        supports = sorted(
            supports_by_pid[pid].values(),
            key=lambda support: (support.rank, support.engine),
        )
        fused.append(
            FusedEvidenceCandidate(
                question_id=question_id,
                paragraph_id=pid,
                title=candidate.title,
                page=candidate.page,
                text=candidate.text,
                fusion_score=float(fusion_score),
                fusion_rank=fusion_rank,
                support_count=support_count,
                supports=supports,
                relevance=relevance,
            )
        )

    return fused


__all__ = ["fuse_candidates_for_question"]
