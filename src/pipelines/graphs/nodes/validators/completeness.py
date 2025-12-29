"""Completeness validator node (Milestone 7).

Produces the final validated evidence bundle by selecting candidates that passed
existence + relevance constraints.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping

from evidence.validators.completeness import (
    CompletenessValidatorConfig,
    compute_completeness,
)
from evidence.validators.selectors import select_passed_candidates
from schemas.internal.evidence import FusedEvidenceBundle, FusedEvidenceCandidate
from schemas.internal.rob2 import QuestionSet


def completeness_validator_node(state: dict) -> dict:
    raw_questions = state.get("question_set")
    if raw_questions is None:
        raise ValueError("completeness_validator_node requires 'question_set'.")
    question_set = QuestionSet.model_validate(raw_questions)

    raw_candidates = state.get("existence_candidates")
    source_key = "existence_candidates"
    if raw_candidates is None:
        raw_candidates = state.get("relevance_candidates")
        source_key = "relevance_candidates"
    if raw_candidates is None:
        return {
            "validated_candidates": {},
            "validated_evidence": [],
            "completeness_passed": True,
            "completeness_failed_questions": [],
            "completeness_report": [],
            "completeness_config": {"source": source_key},
        }
    if not isinstance(raw_candidates, Mapping):
        raise ValueError(f"{source_key} must be a mapping")

    top_k = int(state.get("validated_top_k") or state.get("top_k") or 5)
    if top_k < 1:
        raise ValueError("validated_top_k must be >= 1")

    min_conf_raw = state.get("relevance_min_confidence")
    min_confidence = 0.6 if min_conf_raw is None else float(str(min_conf_raw))

    require_relevance_raw = state.get("completeness_require_relevance")
    if require_relevance_raw is None:
        require_relevance = state.get("relevance_mode") != "none"
    else:
        require_relevance = bool(require_relevance_raw)

    validated_by_q: Dict[str, List[FusedEvidenceCandidate]] = {}
    bundles: List[dict] = []

    question_ids = _ordered_question_ids(question_set, raw_candidates)
    for question_id in question_ids:
        raw_list = raw_candidates.get(question_id)
        if not isinstance(raw_list, list) or not raw_list:
            validated_by_q[question_id] = []
            bundles.append(
                FusedEvidenceBundle(question_id=question_id, items=[]).model_dump()
            )
            continue
        parsed = [FusedEvidenceCandidate.model_validate(item) for item in raw_list]
        if require_relevance:
            passed = select_passed_candidates(
                parsed, min_relevance_confidence=min_confidence
            )
        else:
            passed = [
                candidate
                for candidate in parsed
                if candidate.existence is None or candidate.existence.label == "pass"
            ]
        validated_by_q[question_id] = passed
        bundles.append(
            FusedEvidenceBundle(question_id=question_id, items=passed[:top_k]).model_dump()
        )

    enforce = bool(state.get("completeness_enforce") or False)
    required_raw = state.get("completeness_required_questions")
    required_ids: set[str] | None = None
    if required_raw is not None:
        if not isinstance(required_raw, list) or not all(
            isinstance(item, str) for item in required_raw
        ):
            raise ValueError("completeness_required_questions must be a list[str]")
        required_ids = {item for item in required_raw if item.strip()}

    min_passed_raw = state.get("completeness_min_passed_per_question")
    min_passed = 1 if min_passed_raw is None else int(str(min_passed_raw))

    passed, items, failed = compute_completeness(
        question_set,
        validated_by_q,
        config=CompletenessValidatorConfig(
            enforce=enforce,
            required_question_ids=required_ids,
            min_passed_per_question=min_passed,
        ),
    )

    return {
        "validated_candidates": {
            question_id: [candidate.model_dump() for candidate in candidates]
            for question_id, candidates in validated_by_q.items()
        },
        "validated_evidence": bundles,
        "completeness_passed": passed,
        "completeness_failed_questions": failed,
        "completeness_report": [item.model_dump() for item in items],
        "completeness_config": {
            "source": source_key,
            "validated_top_k": top_k,
            "relevance_min_confidence": min_confidence,
            "require_relevance": require_relevance,
            "enforce": enforce,
            "required_questions": sorted(required_ids) if required_ids else None,
            "min_passed_per_question": min_passed,
        },
    }


def _ordered_question_ids(question_set: QuestionSet, payload: Mapping[str, Any]) -> List[str]:
    union = {key for key in payload.keys() if isinstance(key, str)}
    ordered = [
        question.question_id
        for question in question_set.questions
        if question.question_id in union
    ]
    remaining = sorted(union - set(ordered))
    return [*ordered, *remaining]


__all__ = ["completeness_validator_node"]
