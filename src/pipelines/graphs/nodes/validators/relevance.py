"""LLM-based relevance validator node (Milestone 7).

Annotates fused candidates per question with a relevance verdict and emits a
top-k bundle for downstream reasoning.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping

from core.config import get_settings
from evidence.validators.relevance import (
    LLMRelevanceValidatorConfig,
    RelevanceValidationConfig,
    annotate_relevance,
)
from schemas.internal.evidence import (
    FusedEvidenceCandidate,
    RelevanceAnnotatedFusedEvidenceCandidate,
    RelevanceEvidenceBundle,
    RelevanceVerdict,
)
from schemas.internal.rob2 import QuestionSet


def relevance_validator_node(state: dict) -> dict:
    raw_questions = state.get("question_set")
    if raw_questions is None:
        raise ValueError("relevance_validator_node requires 'question_set'.")

    raw_candidates = state.get("fusion_candidates")
    if raw_candidates is None:
        return {
            "relevance_candidates": {},
            "relevance_evidence": [],
            "relevance_validator": {"requested": "none", "used": "none", "error": None},
            "relevance_config": {},
            "relevance_debug": {},
        }
    if not isinstance(raw_candidates, Mapping):
        raise ValueError("fusion_candidates must be a mapping")

    question_set = QuestionSet.model_validate(raw_questions)
    question_text_by_id = {
        question.question_id: question.text for question in question_set.questions
    }

    top_k = int(state.get("relevance_top_k") or state.get("top_k") or 5)
    if top_k < 1:
        raise ValueError("relevance_top_k must be >= 1")

    top_n = int(state.get("relevance_top_n") or top_k)
    if top_n < 1:
        raise ValueError("relevance_top_n must be >= 1")

    fill_to_top_k = state.get("relevance_fill_to_top_k")
    fill = True if fill_to_top_k is None else bool(fill_to_top_k)

    min_conf_raw = state.get("relevance_min_confidence")
    min_confidence = 0.6 if min_conf_raw is None else float(str(min_conf_raw))
    require_quote_raw = state.get("relevance_require_quote")
    require_quote = True if require_quote_raw is None else bool(require_quote_raw)

    validation_config = RelevanceValidationConfig(
        min_confidence=min_confidence,
        require_supporting_quote=require_quote,
    )

    settings = get_settings()
    requested = str(state.get("relevance_validator") or "none").strip().lower()
    if requested not in {"none", "llm"}:
        raise ValueError("relevance_validator must be 'none' or 'llm'")

    llm = state.get("relevance_llm") if requested == "llm" else None

    used = requested
    error: str | None = None
    model_id: str | None = None
    model_provider: str | None = None
    llm_config: LLMRelevanceValidatorConfig | None = None

    if requested == "llm":
        model_id = str(
            state.get("relevance_model") or settings.relevance_model or ""
        ).strip()
        model_provider = (
            state.get("relevance_model_provider") or settings.relevance_model_provider
        )
        temperature_raw = state.get("relevance_temperature")
        temperature = (
            settings.relevance_temperature
            if temperature_raw is None
            else float(str(temperature_raw))
        )
        timeout_raw = state.get("relevance_timeout")
        timeout = (
            settings.relevance_timeout if timeout_raw is None else float(str(timeout_raw))
        )
        max_tokens_raw = state.get("relevance_max_tokens")
        max_tokens = (
            settings.relevance_max_tokens
            if max_tokens_raw is None
            else int(str(max_tokens_raw))
        )
        max_retries_raw = state.get("relevance_max_retries")
        max_retries = (
            settings.relevance_max_retries
            if max_retries_raw is None
            else int(str(max_retries_raw))
        )

        if not model_id and llm is None:
            used = "none"
            error = (
                "Missing relevance model (set RELEVANCE_MODEL or state['relevance_model'])."
            )
        else:
            llm_config = LLMRelevanceValidatorConfig(
                model=model_id,
                model_provider=str(model_provider) if model_provider else None,
                temperature=temperature,
                timeout=timeout,
                max_tokens=max_tokens,
                max_retries=max_retries,
            )

    question_ids = _ordered_question_ids(question_set, raw_candidates)
    candidates_by_q: Dict[str, List[dict]] = {}
    bundles: List[dict] = []
    debug: Dict[str, dict] = {}

    for question_id in question_ids:
        raw_list = raw_candidates.get(question_id)
        if not isinstance(raw_list, list) or not raw_list:
            continue

        fused = [FusedEvidenceCandidate.model_validate(item) for item in raw_list]
        to_validate = fused[:top_n]
        skipped = fused[top_n:]
        question_text = question_text_by_id.get(question_id) or question_id

        annotated_validated = annotate_relevance(
            question_text,
            to_validate,
            llm=llm,
            llm_config=llm_config,
            config=validation_config,
        )
        annotated_skipped = [
            RelevanceAnnotatedFusedEvidenceCandidate(
                **candidate.model_dump(),
                relevance=RelevanceVerdict(
                    label="unknown",
                    confidence=None,
                    supporting_quote=None,
                ),
            )
            for candidate in skipped
        ]
        annotated = [*annotated_validated, *annotated_skipped]
        candidates_by_q[question_id] = [candidate.model_dump() for candidate in annotated]

        passed = [
            candidate
            for candidate in annotated
            if candidate.relevance.label == "relevant"
            and (candidate.relevance.confidence or 0.0) >= min_confidence
        ]

        selected: List[RelevanceAnnotatedFusedEvidenceCandidate] = passed[:top_k]
        fallback_used = False
        if fill and len(selected) < top_k:
            seen = {candidate.paragraph_id for candidate in selected}
            for candidate in annotated:
                if candidate.paragraph_id in seen:
                    continue
                selected.append(candidate)
                seen.add(candidate.paragraph_id)
                fallback_used = True
                if len(selected) >= top_k:
                    break

        bundles.append(
            RelevanceEvidenceBundle(question_id=question_id, items=selected).model_dump()
        )
        debug[question_id] = {
            "validated": len(to_validate),
            "skipped": len(skipped),
            "passed": len(passed),
            "fallback_used": fallback_used,
        }

    return {
        "relevance_candidates": candidates_by_q,
        "relevance_evidence": bundles,
        "relevance_validator": {
            "requested": requested,
            "used": used,
            "model": model_id,
            "model_provider": model_provider,
            "error": error,
        },
        "relevance_config": {
            "top_k": top_k,
            "top_n": top_n,
            "min_confidence": min_confidence,
            "require_quote": require_quote,
            "fill_to_top_k": fill,
        },
        "relevance_debug": debug,
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


__all__ = ["relevance_validator_node"]
