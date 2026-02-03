"""Evidence fusion node (Milestone 6).

Merges candidates from multiple locator engines into a single ranked list per
question_id, with source attribution.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping

from evidence.fusion import fuse_candidates_for_question
from schemas.internal.evidence import EvidenceCandidate, FusedEvidenceBundle
from schemas.internal.rob2 import QuestionSet
from pipelines.graphs.nodes.retry_utils import (
    filter_question_set,
    merge_bundles,
    merge_by_question,
    read_retry_question_ids,
)


def fusion_node(state: dict) -> dict:
    """LangGraph node: fuse multi-engine candidates into top-k evidence bundles."""
    raw_candidates: Dict[str, Mapping[str, Any]] = {
        "rule_based": state.get("rule_based_candidates") or {},
        "bm25": state.get("bm25_candidates") or {},
        "splade": state.get("splade_candidates") or {},
        "fulltext": state.get("fulltext_candidates") or {},
    }

    engines_present = {
        engine: payload
        for engine, payload in raw_candidates.items()
        if isinstance(payload, Mapping) and payload
    }
    if not engines_present:
        return {
            "fusion_candidates": {},
            "fusion_evidence": [],
            "fusion_config": {"engines": [], "top_k": int(state.get("top_k") or 5)},
        }

    top_k = int(state.get("fusion_top_k") or state.get("top_k") or 5)
    if top_k < 1:
        raise ValueError("fusion_top_k must be >= 1")

    rrf_k = int(state.get("fusion_rrf_k") or 60)
    engine_weights = state.get("fusion_engine_weights")
    weights: Dict[str, float] | None = None
    if engine_weights is not None:
        if not isinstance(engine_weights, Mapping):
            raise ValueError("fusion_engine_weights must be a mapping")
        weights = {str(k): float(v) for k, v in engine_weights.items()}

    retry_ids = read_retry_question_ids(state)
    question_ids = _ordered_question_ids(state, engines_present.values())
    raw_questions = state.get("question_set")
    if retry_ids:
        if raw_questions is not None:
            try:
                question_set = QuestionSet.model_validate(raw_questions)
                filtered = filter_question_set(question_set, retry_ids)
                question_ids = [q.question_id for q in filtered.questions]
                missing = sorted(retry_ids - set(question_ids))
                question_ids.extend(missing)
            except Exception:
                question_ids = [qid for qid in question_ids if qid in retry_ids]
        else:
            question_ids = [qid for qid in question_ids if qid in retry_ids]

    fused_candidates: Dict[str, List[dict]] = {}
    bundles: List[dict] = []
    for question_id in question_ids:
        per_engine: Dict[str, List[EvidenceCandidate]] = {}
        for engine, payload in engines_present.items():
            raw_list = payload.get(question_id)
            if not isinstance(raw_list, list) or not raw_list:
                continue
            per_engine[engine] = [
                EvidenceCandidate.model_validate(item) for item in raw_list
            ]

        fused = fuse_candidates_for_question(
            question_id,
            candidates_by_engine=per_engine,
            rrf_k=rrf_k,
            engine_weights=weights,
        )
        fused_candidates[question_id] = [item.model_dump() for item in fused]
        bundles.append(
            FusedEvidenceBundle(question_id=question_id, items=fused[:top_k]).model_dump()
        )

    if retry_ids:
        fused_candidates = merge_by_question(
            state.get("fusion_candidates"), fused_candidates, retry_ids
        )
        if raw_questions is not None:
            try:
                question_set = QuestionSet.model_validate(raw_questions)
                bundles = merge_bundles(state.get("fusion_evidence"), bundles, question_set)
            except Exception:
                pass

    return {
        "fusion_candidates": fused_candidates,
        "fusion_evidence": bundles,
        "fusion_config": {
            "engines": list(engines_present.keys()),
            "top_k": top_k,
            "rrf_k": rrf_k,
            "engine_weights": weights,
        },
    }


def _ordered_question_ids(
    state: dict,
    candidate_payloads: Iterable[Mapping[str, Any]],
) -> List[str]:
    """Return question_ids in planner order when available, else sorted."""
    union: set[str] = set()
    for payload in candidate_payloads:
        for key in payload.keys():
            if isinstance(key, str):
                union.add(key)

    raw_questions = state.get("question_set")
    if raw_questions is None:
        return sorted(union)

    try:
        question_set = QuestionSet.model_validate(raw_questions)
    except Exception:
        return sorted(union)

    ordered = [question.question_id for question in question_set.questions if question.question_id in union]
    remaining = sorted(union - set(ordered))
    return [*ordered, *remaining]


__all__ = ["fusion_node"]
