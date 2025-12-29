"""LLM-based D1 (Randomization) domain reasoning node (Milestone 8)."""

from __future__ import annotations

from typing import Mapping

from pipelines.graphs.nodes.domains.common import (
    build_reasoning_config,
    get_domain_defaults,
    run_domain_reasoning,
)
from schemas.internal.decisions import DomainDecision
from schemas.internal.rob2 import QuestionSet


def d1_randomization_node(state: dict) -> dict:
    raw_questions = state.get("question_set")
    if raw_questions is None:
        raise ValueError("d1_randomization_node requires 'question_set'.")
    question_set = QuestionSet.model_validate(raw_questions)

    raw_candidates = state.get("validated_candidates")
    if raw_candidates is None:
        raise ValueError("d1_randomization_node requires 'validated_candidates'.")
    if not isinstance(raw_candidates, Mapping):
        raise ValueError("validated_candidates must be a mapping")

    llm = state.get("d1_llm")
    defaults = get_domain_defaults("D1")
    model_id = str(state.get("d1_model") or defaults["model"] or "").strip()
    model_provider = state.get("d1_model_provider") or defaults["model_provider"]
    temperature = (
        defaults["temperature"]
        if state.get("d1_temperature") is None
        else float(str(state.get("d1_temperature")))
    )
    timeout = (
        defaults["timeout"]
        if state.get("d1_timeout") is None
        else float(str(state.get("d1_timeout")))
    )
    max_tokens = (
        defaults["max_tokens"]
        if state.get("d1_max_tokens") is None
        else int(str(state.get("d1_max_tokens")))
    )
    max_retries = (
        defaults["max_retries"]
        if state.get("d1_max_retries") is None
        else int(str(state.get("d1_max_retries")))
    )

    if llm is None and not model_id:
        raise ValueError("Missing D1 model (set D1_MODEL or state['d1_model']).")

    config = build_reasoning_config(
        model_id=model_id,
        model_provider=str(model_provider) if model_provider else None,
        temperature=float(temperature),
        timeout=float(timeout) if timeout is not None else None,
        max_tokens=int(max_tokens) if max_tokens is not None else None,
        max_retries=int(max_retries),
    )

    decision: DomainDecision = run_domain_reasoning(
        domain="D1",
        question_set=question_set,
        validated_candidates=raw_candidates,
        llm=llm,
        llm_config=None if llm is not None else config,
        evidence_top_k=int(state.get("domain_evidence_top_k") or 5),
    )

    return {
        "d1_decision": decision.model_dump(),
        "d1_config": {
            "model": model_id,
            "model_provider": model_provider,
            "temperature": temperature,
            "timeout": timeout,
            "max_tokens": max_tokens,
            "max_retries": max_retries,
        },
    }


__all__ = ["d1_randomization_node"]
