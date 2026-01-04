"""LLM-based D2 (Deviations from intended interventions) domain reasoning node."""

from __future__ import annotations

from typing import Mapping, cast

from pipelines.graphs.nodes.domains.common import (
    EffectType,
    read_domain_llm_config,
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
    config, config_report = read_domain_llm_config(state, prefix="d2")
    if llm is None and not config.model:
        raise ValueError("Missing D2 model (set D2_MODEL or state['d2_model']).")

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
            **config_report,
            "effect_type": effect_type,
        },
    }


__all__ = ["d2_deviations_node"]
