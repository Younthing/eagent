"""ROB2 LangGraph workflow assembly.

This graph currently covers preprocessing, question planning, evidence location
(rule-based + retrieval), fusion, and Milestone 7 validation with retry/rollback
to evidence location on validation failure.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, Dict, Literal, cast

from typing_extensions import TypedDict

from langgraph.graph import END, START, StateGraph

from pipelines.graphs.nodes.fusion import fusion_node
from pipelines.graphs.nodes.locators.retrieval_bm25 import bm25_retrieval_locator_node
from pipelines.graphs.nodes.locators.retrieval_splade import (
    splade_retrieval_locator_node,
)
from pipelines.graphs.nodes.locators.rule_based import rule_based_locator_node
from pipelines.graphs.nodes.planner import planner_node
from pipelines.graphs.nodes.preprocess import preprocess_node
from pipelines.graphs.nodes.validators.completeness import completeness_validator_node
from pipelines.graphs.nodes.validators.consistency import consistency_validator_node
from pipelines.graphs.nodes.validators.existence import existence_validator_node
from pipelines.graphs.nodes.validators.relevance import relevance_validator_node
from pipelines.graphs.routing import validation_should_retry


class Rob2GraphState(TypedDict, total=False):
    pdf_path: str
    doc_structure: dict
    question_set: dict

    top_k: int
    per_query_top_n: int
    rrf_k: int
    query_planner: Literal["deterministic", "llm"]
    reranker: Literal["none", "cross_encoder"]
    use_structure: bool
    splade_model_id: str

    fusion_top_k: int
    fusion_rrf_k: int

    relevance_mode: Literal["none", "llm"]
    relevance_validator: dict
    relevance_min_confidence: float
    relevance_require_quote: bool
    relevance_fill_to_top_k: bool
    relevance_llm: object

    existence_require_text_match: bool
    existence_require_quote_in_source: bool

    consistency_mode: Literal["none", "llm"]
    consistency_validator: dict
    consistency_min_confidence: float
    consistency_llm: object

    completeness_enforce: bool
    completeness_min_passed_per_question: int
    completeness_require_relevance: bool

    rule_based_candidates: dict
    bm25_candidates: dict
    splade_candidates: dict
    fusion_candidates: dict
    relevance_candidates: dict
    existence_candidates: dict

    validated_evidence: list[dict]
    completeness_passed: bool
    completeness_failed_questions: list[str]
    consistency_failed_questions: list[str]

    validation_attempt: int
    validation_max_retries: int
    validation_fail_on_consistency: bool
    validation_relax_on_retry: bool
    validation_retry_log: Annotated[list[dict], operator.add]


NodeFn = object


def _init_validation_state_node(state: Rob2GraphState) -> dict:
    attempt = state.get("validation_attempt")
    max_retries = state.get("validation_max_retries")
    fail_on_consistency = state.get("validation_fail_on_consistency")
    relax_on_retry = state.get("validation_relax_on_retry")
    require_relevance = state.get("completeness_require_relevance")
    relevance_mode = state.get("relevance_mode")
    return {
        "validation_attempt": 0 if attempt is None else int(attempt),
        "validation_max_retries": 1 if max_retries is None else int(max_retries),
        "validation_fail_on_consistency": True
        if fail_on_consistency is None
        else bool(fail_on_consistency),
        "validation_relax_on_retry": True
        if relax_on_retry is None
        else bool(relax_on_retry),
        "validation_retry_log": [],
        "completeness_enforce": False
        if state.get("completeness_enforce") is None
        else bool(state.get("completeness_enforce")),
        "completeness_require_relevance": False
        if require_relevance is None and relevance_mode == "none"
        else bool(require_relevance)
        if require_relevance is not None
        else True,
    }


def _prepare_validation_retry_node(state: Rob2GraphState) -> dict:
    attempt = int(state.get("validation_attempt") or 0) + 1
    max_retries = int(state.get("validation_max_retries") or 0)
    failed_questions = state.get("completeness_failed_questions") or []
    consistency_failed = state.get("consistency_failed_questions") or []
    relax_on_retry = bool(state.get("validation_relax_on_retry", True))

    per_query_top_n = int(state.get("per_query_top_n") or 50)
    top_k = int(state.get("top_k") or 5)
    use_structure = bool(state.get("use_structure", True))

    updates: Dict[str, Any] = {}
    if attempt == 1 and use_structure:
        updates["use_structure"] = False
    if attempt >= 1:
        updates["per_query_top_n"] = min(per_query_top_n * 2, 200)
        updates["top_k"] = min(top_k + 3, 10)
        updates["fusion_top_k"] = updates["top_k"]
        if relax_on_retry:
            updates["completeness_require_relevance"] = False
            updates.setdefault("relevance_min_confidence", 0.3)
            updates.setdefault("relevance_require_quote", False)
            updates.setdefault("existence_require_text_match", False)
            updates.setdefault("existence_require_quote_in_source", False)

    return {
        "validation_attempt": attempt,
        "validation_retry_log": [
            {
                "attempt": attempt,
                "max_retries": max_retries,
                "completeness_failed_questions": failed_questions,
                "consistency_failed_questions": consistency_failed,
                "updates": updates,
            }
        ],
        **updates,
    }


def build_rob2_graph(*, node_overrides: dict[str, NodeFn] | None = None):
    """Build and compile the ROB2 workflow graph."""
    overrides = node_overrides or {}
    builder: StateGraph = StateGraph(cast(Any, Rob2GraphState))

    builder.add_node(
        "preprocess", cast(Any, overrides.get("preprocess") or preprocess_node)
    )
    builder.add_node("planner", cast(Any, overrides.get("planner") or planner_node))
    builder.add_node("init_validation", cast(Any, _init_validation_state_node))

    builder.add_node(
        "rule_based_locator",
        cast(Any, overrides.get("rule_based_locator") or rule_based_locator_node),
    )
    builder.add_node(
        "bm25_locator",
        cast(Any, overrides.get("bm25_locator") or bm25_retrieval_locator_node),
    )
    builder.add_node(
        "splade_locator",
        cast(Any, overrides.get("splade_locator") or splade_retrieval_locator_node),
    )
    builder.add_node("fusion", cast(Any, overrides.get("fusion") or fusion_node))

    builder.add_node(
        "relevance_validator",
        cast(Any, overrides.get("relevance_validator") or relevance_validator_node),
    )
    builder.add_node(
        "existence_validator",
        cast(Any, overrides.get("existence_validator") or existence_validator_node),
    )
    builder.add_node(
        "consistency_validator",
        cast(Any, overrides.get("consistency_validator") or consistency_validator_node),
    )
    builder.add_node(
        "completeness_validator",
        cast(
            Any, overrides.get("completeness_validator") or completeness_validator_node
        ),
    )

    builder.add_node("prepare_retry", cast(Any, _prepare_validation_retry_node))

    builder.add_edge(START, "preprocess")
    builder.add_edge("preprocess", "planner")
    builder.add_edge("planner", "init_validation")

    builder.add_edge("init_validation", "rule_based_locator")
    builder.add_edge("rule_based_locator", "bm25_locator")
    builder.add_edge("bm25_locator", "splade_locator")
    builder.add_edge("splade_locator", "fusion")
    builder.add_edge("fusion", "relevance_validator")
    builder.add_edge("relevance_validator", "existence_validator")
    builder.add_edge("existence_validator", "consistency_validator")
    builder.add_edge("consistency_validator", "completeness_validator")

    builder.add_conditional_edges(
        "completeness_validator",
        validation_should_retry,
        {"retry": "prepare_retry", "end": END},
    )
    builder.add_edge("prepare_retry", "rule_based_locator")

    return builder.compile()


__all__ = ["Rob2GraphState", "build_rob2_graph"]
