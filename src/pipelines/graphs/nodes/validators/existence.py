"""Deterministic existence validator node (Milestone 7)."""

from __future__ import annotations

from typing import Any, Dict, List, Mapping

from evidence.validators.existence import ExistenceValidatorConfig, annotate_existence
from schemas.internal.documents import DocStructure
from schemas.internal.evidence import FusedEvidenceBundle, FusedEvidenceCandidate
from schemas.internal.rob2 import QuestionSet
from pipelines.graphs.nodes.retry_utils import (
    filter_question_set,
    merge_bundles,
    merge_by_question,
    read_retry_question_ids,
)


def existence_validator_node(state: dict) -> dict:
    raw_doc = state.get("doc_structure")
    if raw_doc is None:
        raise ValueError("existence_validator_node requires 'doc_structure'.")
    doc_structure = DocStructure.model_validate(raw_doc)

    raw_questions = state.get("question_set")
    if raw_questions is None:
        raise ValueError("existence_validator_node requires 'question_set'.")
    question_set = QuestionSet.model_validate(raw_questions)

    raw_candidates = state.get("relevance_candidates")
    source_key = "relevance_candidates"
    if raw_candidates is None:
        raw_candidates = state.get("fusion_candidates")
        source_key = "fusion_candidates"
    if raw_candidates is None:
        return {
            "existence_candidates": {},
            "existence_evidence": [],
            "existence_debug": {},
            "existence_config": {"source": source_key},
        }
    if not isinstance(raw_candidates, Mapping):
        raise ValueError(f"{source_key} must be a mapping")

    top_k = int(state.get("existence_top_k") or state.get("top_k") or 5)
    if top_k < 1:
        raise ValueError("existence_top_k must be >= 1")

    require_text_match = state.get("existence_require_text_match")
    require_quote_in_source = state.get("existence_require_quote_in_source")
    config = ExistenceValidatorConfig(
        require_text_match=True if require_text_match is None else bool(require_text_match),
        require_quote_in_source=True
        if require_quote_in_source is None
        else bool(require_quote_in_source),
    )

    retry_ids = read_retry_question_ids(state)
    question_ids = _ordered_question_ids(state, raw_candidates)
    if retry_ids:
        filtered = filter_question_set(question_set, retry_ids)
        question_ids = [question.question_id for question in filtered.questions]
        missing = sorted(retry_ids - set(question_ids))
        question_ids.extend(missing)
    candidates_by_q: Dict[str, List[dict]] = {}
    bundles: List[dict] = []
    debug: Dict[str, dict] = {}

    for question_id in question_ids:
        raw_list = raw_candidates.get(question_id)
        if not isinstance(raw_list, list) or not raw_list:
            candidates_by_q[question_id] = []
            bundles.append(
                FusedEvidenceBundle(question_id=question_id, items=[]).model_dump()
            )
            debug[question_id] = {"total": 0, "passed": 0, "failed": 0}
            continue
        parsed = [FusedEvidenceCandidate.model_validate(item) for item in raw_list]
        annotated = annotate_existence(doc_structure, parsed, config=config)

        passed = [
            candidate
            for candidate in annotated
            if candidate.existence is not None and candidate.existence.label == "pass"
        ]
        bundles.append(FusedEvidenceBundle(question_id=question_id, items=passed[:top_k]).model_dump())
        candidates_by_q[question_id] = [candidate.model_dump() for candidate in annotated]
        debug[question_id] = {
            "total": len(annotated),
            "passed": len(passed),
            "failed": len(annotated) - len(passed),
        }

    if retry_ids:
        candidates_by_q = merge_by_question(
            state.get("existence_candidates"), candidates_by_q, retry_ids
        )
        bundles = merge_bundles(state.get("existence_evidence"), bundles, question_set)
        debug = merge_by_question(state.get("existence_debug"), debug, retry_ids)

    return {
        "existence_candidates": candidates_by_q,
        "existence_evidence": bundles,
        "existence_debug": debug,
        "existence_config": {
            "source": source_key,
            "top_k": top_k,
            "require_text_match": config.require_text_match,
            "require_quote_in_source": config.require_quote_in_source,
        },
    }


def _ordered_question_ids(state: dict, payload: Mapping[str, Any]) -> List[str]:
    union = {key for key in payload.keys() if isinstance(key, str)}
    raw_questions = state.get("question_set")
    if raw_questions is None:
        return sorted(union)

    try:
        question_set = QuestionSet.model_validate(raw_questions)
    except Exception:
        return sorted(union)

    ordered = [
        question.question_id
        for question in question_set.questions
        if question.question_id in union
    ]
    remaining = sorted(union - set(ordered))
    return [*ordered, *remaining]


__all__ = ["existence_validator_node"]
