"""LLM-based D1 (Randomization) domain reasoning node (Milestone 8)."""

from __future__ import annotations

from typing import Mapping

from pipelines.graphs.nodes.domains.common import (
    read_domain_llm_config,
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
    config, config_report = read_domain_llm_config(state, prefix="d1")
    if llm is None and not config.model:
        raise ValueError("Missing D1 model (set D1_MODEL or state['d1_model']).")

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
        "d1_config": config_report,
    }


__all__ = ["d1_randomization_node"]
