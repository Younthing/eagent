"""LLM-based D2 (Deviations from intended interventions) domain reasoning node."""

from __future__ import annotations

from typing import Mapping, cast

from pipelines.graphs.nodes.domains.common import (
    EffectType,
    build_reasoning_config,
    get_domain_defaults,
    run_domain_reasoning,
)
from schemas.internal.decisions import DomainDecision
from schemas.internal.rob2 import QuestionSet


def d2_deviations_node(state: dict) -> dict:
    raw_questions = state.get("question_set")
    if raw_questions is None:
        raise ValueError("d2_deviations_node requires 'question_set'.")
    question_set = QuestionSet.model_validate(raw_questions)

    raw_candidates = state.get("validated_candidates")
    if raw_candidates is None:
        raise ValueError("d2_deviations_node requires 'validated_candidates'.")
    if not isinstance(raw_candidates, Mapping):
        raise ValueError("validated_candidates must be a mapping")

    effect_type = str(state.get("d2_effect_type") or "assignment").strip().lower()
    if effect_type not in {"assignment", "adherence"}:
        raise ValueError("d2_effect_type must be 'assignment' or 'adherence'")
    effect_type = cast(EffectType, effect_type)

    llm = state.get("d2_llm")
    defaults = get_domain_defaults("D2")
    model_id = str(state.get("d2_model") or defaults["model"] or "").strip()
    model_provider = state.get("d2_model_provider") or defaults["model_provider"]
    temperature = (
        defaults["temperature"]
        if state.get("d2_temperature") is None
        else float(str(state.get("d2_temperature")))
    )
    timeout = (
        defaults["timeout"]
        if state.get("d2_timeout") is None
        else float(str(state.get("d2_timeout")))
    )
    max_tokens = (
        defaults["max_tokens"]
        if state.get("d2_max_tokens") is None
        else int(str(state.get("d2_max_tokens")))
    )
    max_retries = (
        defaults["max_retries"]
        if state.get("d2_max_retries") is None
        else int(str(state.get("d2_max_retries")))
    )

    if llm is None and not model_id:
        raise ValueError("Missing D2 model (set D2_MODEL or state['d2_model']).")

    config = build_reasoning_config(
        model_id=model_id,
        model_provider=str(model_provider) if model_provider else None,
        temperature=float(temperature),
        timeout=float(timeout) if timeout is not None else None,
        max_tokens=int(max_tokens) if max_tokens is not None else None,
        max_retries=int(max_retries),
    )

    decision: DomainDecision = run_domain_reasoning(
        domain="D2",
        question_set=question_set,
        validated_candidates=raw_candidates,
        llm=llm,
        llm_config=None if llm is not None else config,
        effect_type=effect_type,
        evidence_top_k=int(state.get("domain_evidence_top_k") or 5),
    )

    return {
        "d2_decision": decision.model_dump(),
        "d2_config": {
            "model": model_id,
            "model_provider": model_provider,
            "temperature": temperature,
            "timeout": timeout,
            "max_tokens": max_tokens,
            "max_retries": max_retries,
            "effect_type": effect_type,
        },
    }


__all__ = ["d2_deviations_node"]
