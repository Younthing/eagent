"""ROB2 LangGraph workflow assembly.

This graph currently covers preprocessing, question planning, evidence location
(rule-based + retrieval), fusion, Milestone 7 validation with retry/rollback,
Milestone 8 D1–D5 reasoning, and an optional Milestone 9 full-text audit step.
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
from pipelines.graphs.nodes.locators.llm_locator import llm_locator_node
from pipelines.graphs.nodes.locators.rule_based import rule_based_locator_node
from pipelines.graphs.nodes.planner import planner_node
from pipelines.graphs.nodes.preprocess import preprocess_node
from pipelines.graphs.nodes.domains.d1_randomization import d1_randomization_node
from pipelines.graphs.nodes.domains.d2_deviations import d2_deviations_node
from pipelines.graphs.nodes.domains.d3_missing_data import d3_missing_data_node
from pipelines.graphs.nodes.domains.d4_measurement import d4_measurement_node
from pipelines.graphs.nodes.domains.d5_reporting import d5_reporting_node
from pipelines.graphs.nodes.domain_audit import (
    d1_audit_node,
    d2_audit_node,
    d3_audit_node,
    d4_audit_node,
    d5_audit_node,
    final_domain_audit_node,
)
from pipelines.graphs.nodes.aggregate import aggregate_node
from pipelines.graphs.nodes.validators.completeness import completeness_validator_node
from pipelines.graphs.nodes.validators.consistency import consistency_validator_node
from pipelines.graphs.nodes.validators.existence import existence_validator_node
from pipelines.graphs.nodes.validators.relevance import relevance_validator_node
from pipelines.graphs.routing import (
    domain_audit_should_run,
    domain_audit_should_run_final,
    validation_should_retry,
)


class Rob2GraphState(TypedDict, total=False):
    pdf_path: str
    doc_hash: str
    doc_structure: dict
    question_set: dict
    docling_layout_model: str
    docling_artifacts_path: str
    docling_chunker_model: str
    docling_chunker_max_tokens: int
    docling_images_scale: float
    docling_generate_page_images: bool
    docling_generate_picture_images: bool
    docling_do_picture_classification: bool
    docling_do_picture_description: bool
    docling_picture_description_preset: str
    figure_description_mode: Literal["none", "llm"]
    figure_description_model: str
    figure_description_model_provider: str
    figure_description_max_images: int
    figure_description_max_tokens: int
    figure_description_timeout: float
    figure_description_max_retries: int
    preprocess_drop_references: bool
    preprocess_reference_titles: list[str] | str | None
    doc_scope_mode: Literal["auto", "manual", "none"]
    doc_scope_include_paragraph_ids: list[str] | str | None
    doc_scope_page_range: str
    doc_scope_min_pages: int
    doc_scope_min_confidence: float
    doc_scope_abstract_gap_pages: int
    doc_scope_report: dict

    top_k: int
    per_query_top_n: int
    rrf_k: int
    query_planner: Literal["deterministic", "llm"]
    query_planner_model: str
    query_planner_model_provider: str
    query_planner_temperature: float
    query_planner_timeout: float
    query_planner_max_tokens: int
    query_planner_max_retries: int
    query_planner_max_keywords: int
    reranker: Literal["none", "cross_encoder"]
    reranker_model_id: str
    reranker_device: str
    reranker_max_length: int
    reranker_batch_size: int
    rerank_top_n: int
    use_structure: bool
    section_bonus_weight: float
    locator_tokenizer: str
    locator_char_ngram: int
    splade_model_id: str
    splade_device: str
    splade_hf_token: str
    splade_query_max_length: int
    splade_doc_max_length: int
    splade_batch_size: int
    llm_locator_mode: Literal["llm", "none"]
    llm_locator_model: str
    llm_locator_model_provider: str
    llm_locator_temperature: float
    llm_locator_timeout: float
    llm_locator_max_tokens: int
    llm_locator_max_retries: int
    llm_locator_max_steps: int
    llm_locator_seed_top_n: int
    llm_locator_per_step_top_n: int
    llm_locator_max_candidates: int
    llm_locator_llm: object

    fusion_top_k: int
    fusion_rrf_k: int
    fusion_engine_weights: dict

    relevance_mode: Literal["none", "llm"]
    relevance_validator: dict
    relevance_config: dict
    relevance_debug: dict
    relevance_min_confidence: float
    relevance_require_quote: bool
    relevance_fill_to_top_k: bool
    relevance_top_k: int
    relevance_top_n: int
    relevance_model: str
    relevance_model_provider: str
    relevance_temperature: float
    relevance_timeout: float
    relevance_max_tokens: int
    relevance_max_retries: int
    relevance_llm: object
    d1_model: str
    d1_model_provider: str
    d1_temperature: float
    d1_timeout: float
    d1_max_tokens: int
    d1_max_retries: int
    d1_llm: object

    existence_require_text_match: bool
    existence_require_quote_in_source: bool
    existence_top_k: int

    consistency_mode: Literal["none", "llm"]
    consistency_validator: dict
    consistency_config: dict
    consistency_reports: dict
    consistency_min_confidence: float
    consistency_require_quotes_for_fail: bool
    consistency_top_n: int
    consistency_model: str
    consistency_model_provider: str
    consistency_temperature: float
    consistency_timeout: float
    consistency_max_tokens: int
    consistency_max_retries: int
    consistency_llm: object
    d2_model: str
    d2_model_provider: str
    d2_temperature: float
    d2_timeout: float
    d2_max_tokens: int
    d2_max_retries: int
    d2_llm: object
    d2_effect_type: Literal["assignment", "adherence"]

    d3_model: str
    d3_model_provider: str
    d3_temperature: float
    d3_timeout: float
    d3_max_tokens: int
    d3_max_retries: int
    d3_llm: object

    d4_model: str
    d4_model_provider: str
    d4_temperature: float
    d4_timeout: float
    d4_max_tokens: int
    d4_max_retries: int
    d4_llm: object

    d5_model: str
    d5_model_provider: str
    d5_temperature: float
    d5_timeout: float
    d5_max_tokens: int
    d5_max_retries: int
    d5_llm: object

    domain_audit_mode: Literal["none", "llm"]
    domain_audit_model: str
    domain_audit_model_provider: str
    domain_audit_temperature: float
    domain_audit_timeout: float
    domain_audit_max_tokens: int
    domain_audit_max_retries: int
    domain_audit_patch_window: int
    domain_audit_max_patches_per_question: int
    domain_audit_rerun_domains: bool
    domain_audit_final: bool
    domain_audit_llm: object
    domain_audit_report: dict
    domain_audit_reports: Annotated[list[dict], operator.add]

    rob2_result: dict
    rob2_table_markdown: str

    completeness_enforce: bool
    completeness_min_passed_per_question: int
    completeness_require_relevance: bool
    completeness_required_questions: list[str]
    validated_top_k: int
    domain_evidence_top_k: int

    rule_based_candidates: dict
    bm25_candidates: dict
    splade_candidates: dict
    fulltext_candidates: dict
    fusion_candidates: dict
    relevance_candidates: dict
    existence_candidates: dict
    llm_locator_debug: dict

    validated_evidence: list[dict]
    validated_candidates: dict
    completeness_report: list[dict]
    completeness_config: dict
    completeness_passed: bool
    completeness_failed_questions: list[str]
    consistency_failed_questions: list[str]
    d1_decision: dict
    d2_decision: dict
    d3_decision: dict
    d4_decision: dict
    d5_decision: dict

    validation_attempt: int
    validation_max_retries: int
    validation_fail_on_consistency: bool
    validation_relax_on_retry: bool
    validation_retry_log: Annotated[list[dict], operator.add]
    retry_question_ids: list[str]
    fulltext_fallback_used: bool
    cache_manager: object


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
        "validation_max_retries": 3 if max_retries is None else int(max_retries),
        "validation_fail_on_consistency": True
        if fail_on_consistency is None
        else bool(fail_on_consistency),
        "validation_relax_on_retry": True
        if relax_on_retry is None
        else bool(relax_on_retry),
        "validation_retry_log": [],
        "domain_audit_reports": [],
        "domain_audit_final": False
        if state.get("domain_audit_final") is None
        else bool(state.get("domain_audit_final")),
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
    fail_on_consistency = bool(state.get("validation_fail_on_consistency", True))
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

    retry_ids: set[str] = set()
    for item in failed_questions:
        if isinstance(item, str) and item.strip():
            retry_ids.add(item.strip())
    if fail_on_consistency:
        for item in consistency_failed:
            if isinstance(item, str) and item.strip():
                retry_ids.add(item.strip())

    return {
        "validation_attempt": attempt,
        "retry_question_ids": sorted(retry_ids),
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


def _enable_fulltext_fallback_node(state: Rob2GraphState) -> dict:
    """Enable full-text audit fallback when validation retries are exhausted."""
    updates: Dict[str, Any] = {
        "domain_audit_mode": "llm",
        "domain_audit_rerun_domains": True,
        "fulltext_fallback_used": True,
    }
    if state.get("domain_audit_llm") is None and state.get("d1_llm") is not None:
        updates["domain_audit_llm"] = state.get("d1_llm")

    attempt = int(state.get("validation_attempt") or 0)
    max_retries = int(state.get("validation_max_retries") or 0)
    return {
        "validation_retry_log": [
            {
                "event": "fulltext_fallback",
                "attempt": attempt,
                "max_retries": max_retries,
                "completeness_failed_questions": state.get("completeness_failed_questions") or [],
                "consistency_failed_questions": state.get("consistency_failed_questions") or [],
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
    builder.add_node(
        "llm_locator",
        cast(Any, overrides.get("llm_locator") or llm_locator_node),
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
    builder.add_node(
        "d1_randomization",
        cast(Any, overrides.get("d1_randomization") or d1_randomization_node),
    )
    builder.add_node(
        "d2_deviations",
        cast(Any, overrides.get("d2_deviations") or d2_deviations_node),
    )
    builder.add_node(
        "d3_missing_data",
        cast(Any, overrides.get("d3_missing_data") or d3_missing_data_node),
    )
    builder.add_node(
        "d4_measurement",
        cast(Any, overrides.get("d4_measurement") or d4_measurement_node),
    )
    builder.add_node(
        "d5_reporting",
        cast(Any, overrides.get("d5_reporting") or d5_reporting_node),
    )
    builder.add_node(
        "d1_audit",
        cast(Any, overrides.get("d1_audit") or d1_audit_node),
    )
    builder.add_node(
        "d2_audit",
        cast(Any, overrides.get("d2_audit") or d2_audit_node),
    )
    builder.add_node(
        "d3_audit",
        cast(Any, overrides.get("d3_audit") or d3_audit_node),
    )
    builder.add_node(
        "d4_audit",
        cast(Any, overrides.get("d4_audit") or d4_audit_node),
    )
    builder.add_node(
        "d5_audit",
        cast(Any, overrides.get("d5_audit") or d5_audit_node),
    )
    builder.add_node(
        "final_domain_audit",
        cast(Any, overrides.get("final_domain_audit") or final_domain_audit_node),
    )
    builder.add_node(
        "aggregate",
        cast(Any, overrides.get("aggregate") or aggregate_node),
    )

    builder.add_node("prepare_retry", cast(Any, _prepare_validation_retry_node))
    builder.add_node(
        "enable_fulltext_fallback", cast(Any, _enable_fulltext_fallback_node)
    )

    builder.add_edge(START, "preprocess")
    builder.add_edge("preprocess", "planner")
    builder.add_edge("planner", "init_validation")

    builder.add_edge("init_validation", "rule_based_locator")
    builder.add_edge("rule_based_locator", "bm25_locator")
    builder.add_edge("bm25_locator", "splade_locator")
    builder.add_edge("splade_locator", "llm_locator")
    builder.add_edge("llm_locator", "fusion")
    builder.add_edge("fusion", "relevance_validator")
    builder.add_edge("relevance_validator", "existence_validator")
    builder.add_edge("existence_validator", "consistency_validator")
    builder.add_edge("consistency_validator", "completeness_validator")

    builder.add_conditional_edges(
        "completeness_validator",
        validation_should_retry,
        {
            "retry": "prepare_retry",
            "fallback": "enable_fulltext_fallback",
            "proceed": "d1_randomization",
        },
    )
    builder.add_edge("prepare_retry", "rule_based_locator")
    builder.add_edge("enable_fulltext_fallback", "d1_randomization")
    builder.add_conditional_edges(
        "d1_randomization",
        domain_audit_should_run,
        {"audit": "d1_audit", "skip": "d2_deviations"},
    )
    builder.add_edge("d1_audit", "d2_deviations")
    builder.add_conditional_edges(
        "d2_deviations",
        domain_audit_should_run,
        {"audit": "d2_audit", "skip": "d3_missing_data"},
    )
    builder.add_edge("d2_audit", "d3_missing_data")
    builder.add_conditional_edges(
        "d3_missing_data",
        domain_audit_should_run,
        {"audit": "d3_audit", "skip": "d4_measurement"},
    )
    builder.add_edge("d3_audit", "d4_measurement")
    builder.add_conditional_edges(
        "d4_measurement",
        domain_audit_should_run,
        {"audit": "d4_audit", "skip": "d5_reporting"},
    )
    builder.add_edge("d4_audit", "d5_reporting")
    builder.add_conditional_edges(
        "d5_reporting",
        domain_audit_should_run,
        {"audit": "d5_audit", "skip": "aggregate"},
    )
    builder.add_conditional_edges(
        "d5_audit",
        domain_audit_should_run_final,
        {"final": "final_domain_audit", "skip": "aggregate"},
    )
    builder.add_edge("final_domain_audit", "aggregate")
    builder.add_edge("aggregate", END)

    compiled = builder.compile()
    # This graph includes an intentional retry loop (Milestone 7). With additional
    # downstream nodes (M8+), a single retry can exceed LangGraph's default
    # recursion limit (25). Set a higher default to avoid false positives.
    return compiled.with_config({"recursion_limit": 100})


__all__ = ["Rob2GraphState", "build_rob2_graph"]
