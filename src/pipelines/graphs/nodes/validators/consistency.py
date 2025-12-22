"""LLM-based consistency validator node (Milestone 7)."""

from __future__ import annotations

from typing import Any, Dict, List, Mapping

from core.config import get_settings
from evidence.validators.consistency import (
    ConsistencyValidationConfig,
    LLMConsistencyValidatorConfig,
    judge_consistency,
)
from evidence.validators.selectors import select_passed_candidates
from schemas.internal.evidence import ConsistencyVerdict, FusedEvidenceCandidate
from schemas.internal.rob2 import QuestionSet


def consistency_validator_node(state: dict) -> dict:
    raw_questions = state.get("question_set")
    if raw_questions is None:
        raise ValueError("consistency_validator_node requires 'question_set'.")
    question_set = QuestionSet.model_validate(raw_questions)
    question_text_by_id = {
        question.question_id: question.text for question in question_set.questions
    }

    raw_candidates = state.get("existence_candidates")
    source_key = "existence_candidates"
    if raw_candidates is None:
        raw_candidates = state.get("relevance_candidates")
        source_key = "relevance_candidates"
    if raw_candidates is None:
        return {
            "consistency_reports": {},
            "consistency_failed_questions": [],
            "consistency_validator": {"requested": "none", "used": "none", "error": None},
            "consistency_config": {"source": source_key},
        }
    if not isinstance(raw_candidates, Mapping):
        raise ValueError(f"{source_key} must be a mapping")

    top_n = int(state.get("consistency_top_n") or 3)
    if top_n < 2:
        raise ValueError("consistency_top_n must be >= 2")

    min_conf_raw = state.get("consistency_min_confidence")
    min_confidence = 0.6 if min_conf_raw is None else float(str(min_conf_raw))
    require_quotes_raw = state.get("consistency_require_quotes_for_fail")
    require_quotes_for_fail = True if require_quotes_raw is None else bool(require_quotes_raw)
    config = ConsistencyValidationConfig(
        min_confidence=min_confidence,
        require_quotes_for_fail=require_quotes_for_fail,
    )

    settings = get_settings()
    requested = str(state.get("consistency_validator") or "none").strip().lower()
    if requested not in {"none", "llm"}:
        raise ValueError("consistency_validator must be 'none' or 'llm'")

    llm = state.get("consistency_llm") if requested == "llm" else None
    used = requested
    error: str | None = None
    model_id: str | None = None
    model_provider: str | None = None
    llm_config: LLMConsistencyValidatorConfig | None = None

    if requested == "llm":
        model_id = str(
            state.get("consistency_model") or settings.consistency_model or ""
        ).strip()
        model_provider = (
            state.get("consistency_model_provider") or settings.consistency_model_provider
        )
        temperature_raw = state.get("consistency_temperature")
        temperature = (
            settings.consistency_temperature
            if temperature_raw is None
            else float(str(temperature_raw))
        )
        timeout_raw = state.get("consistency_timeout")
        timeout = (
            settings.consistency_timeout
            if timeout_raw is None
            else float(str(timeout_raw))
        )
        max_tokens_raw = state.get("consistency_max_tokens")
        max_tokens = (
            settings.consistency_max_tokens
            if max_tokens_raw is None
            else int(str(max_tokens_raw))
        )
        max_retries_raw = state.get("consistency_max_retries")
        max_retries = (
            settings.consistency_max_retries
            if max_retries_raw is None
            else int(str(max_retries_raw))
        )

        if not model_id and llm is None:
            used = "none"
            error = (
                "Missing consistency model (set CONSISTENCY_MODEL or state['consistency_model'])."
            )
        else:
            llm_config = LLMConsistencyValidatorConfig(
                model=model_id,
                model_provider=str(model_provider) if model_provider else None,
                temperature=temperature,
                timeout=timeout,
                max_tokens=max_tokens,
                max_retries=max_retries,
            )

    reports: Dict[str, dict] = {}
    failed_questions: List[str] = []

    question_ids = _ordered_question_ids(question_set, raw_candidates)
    for question_id in question_ids:
        raw_list = raw_candidates.get(question_id)
        if not isinstance(raw_list, list) or not raw_list:
            reports[question_id] = ConsistencyVerdict(label="unknown", confidence=None, conflicts=[]).model_dump()
            continue

        candidates = [FusedEvidenceCandidate.model_validate(item) for item in raw_list]
        min_conf_raw = state.get("relevance_min_confidence")
        min_confidence = 0.6 if min_conf_raw is None else float(str(min_conf_raw))
        passed = select_passed_candidates(
            candidates, min_relevance_confidence=min_confidence
        )[:top_n]
        if len(passed) < 2:
            reports[question_id] = ConsistencyVerdict(
                label="pass" if passed else "unknown",
                confidence=None,
                conflicts=[],
            ).model_dump()
            continue

        question_text = question_text_by_id.get(question_id) or question_id
        verdict = judge_consistency(
            question_text,
            passed,
            llm=llm,
            llm_config=llm_config,
            config=config,
        )
        reports[question_id] = verdict.model_dump()
        if verdict.label == "fail":
            failed_questions.append(question_id)

    return {
        "consistency_reports": reports,
        "consistency_failed_questions": failed_questions,
        "consistency_validator": {
            "requested": requested,
            "used": used,
            "model": model_id,
            "model_provider": model_provider,
            "error": error,
        },
        "consistency_config": {
            "source": source_key,
            "top_n": top_n,
            "min_confidence": min_confidence,
            "require_quotes_for_fail": require_quotes_for_fail,
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


__all__ = ["consistency_validator_node"]
