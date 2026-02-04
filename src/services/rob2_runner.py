"""Core ROB2 runner service for CLI/API reuse."""

from __future__ import annotations

from time import perf_counter
from pathlib import Path
from typing import Any, Mapping

from core.config import get_settings
from pipelines.graphs.rob2_graph import build_rob2_graph
from retrieval.engines.splade import DEFAULT_SPLADE_MODEL_ID
from retrieval.rerankers.cross_encoder import DEFAULT_CROSS_ENCODER_MODEL_ID
from rob2.locator_rules import get_locator_rules
from schemas.internal.results import Rob2FinalOutput
from schemas.requests import Rob2Input, Rob2RunOptions
from schemas.responses import Rob2RunResult
from services.io import temp_pdf


_DEFAULT_TOP_K = 5
_DEFAULT_PER_QUERY_TOP_N = 50
_DEFAULT_RRF_K = 60
_DEFAULT_RELEVANCE_MIN_CONFIDENCE = 0.6
_DEFAULT_CONSISTENCY_MIN_CONFIDENCE = 0.6
_DEFAULT_CONSISTENCY_TOP_N = 3
_DEFAULT_DOMAIN_EVIDENCE_TOP_K = 5
_DEFAULT_MAX_RETRIES = 3
_DEFAULT_DOMAIN_MAX_RETRIES = 2
_DEFAULT_RERANKER_MAX_LENGTH = 512
_DEFAULT_RERANKER_BATCH_SIZE = 8
_DEFAULT_RERANKER_TOP_N = 50
_DEFAULT_SECTION_BONUS_WEIGHT = 0.25
_DEFAULT_SPLADE_QUERY_MAX = 64
_DEFAULT_SPLADE_DOC_MAX = 256
_DEFAULT_SPLADE_BATCH = 8
_DEFAULT_QUERY_PLANNER_MAX_KEYWORDS = 10
_DEFAULT_AUDIT_PATCH_WINDOW = 0
_DEFAULT_AUDIT_MAX_PATCHES = 3
_DEFAULT_LLM_LOCATOR_MAX_STEPS = 3
_DEFAULT_LLM_LOCATOR_SEED_TOP_N = 5
_DEFAULT_LLM_LOCATOR_PER_STEP_TOP_N = 10
_DEFAULT_LLM_LOCATOR_MAX_CANDIDATES = 40


def run_rob2(
    input_data: Rob2Input | Mapping[str, Any],
    options: Rob2RunOptions | Mapping[str, Any] | None = None,
    *,
    state_overrides: Mapping[str, Any] | None = None,
) -> Rob2RunResult:
    """Run the ROB2 graph with normalized options and return a typed result."""
    input_obj = input_data if isinstance(input_data, Rob2Input) else Rob2Input.model_validate(input_data)
    options_obj = options if isinstance(options, Rob2RunOptions) else Rob2RunOptions.model_validate(options or {})

    start = perf_counter()
    warnings: list[str] = []

    if input_obj.pdf_bytes is not None:
        with temp_pdf(input_obj.pdf_bytes, filename=input_obj.filename) as path:
            state = _build_run_state(str(path), options_obj, warnings)
            state.update(state_overrides or {})
            final_state = _invoke_graph(state)
    else:
        state = _build_run_state(str(input_obj.pdf_path), options_obj, warnings)
        state.update(state_overrides or {})
        final_state = _invoke_graph(state)

    runtime_ms = int((perf_counter() - start) * 1000)
    return _build_result(final_state, options_obj, runtime_ms, warnings)


def _invoke_graph(state: dict[str, Any]) -> dict[str, Any]:
    app = build_rob2_graph()
    return app.invoke(state)


def _build_run_state(
    pdf_path: str | None,
    options: Rob2RunOptions,
    warnings: list[str],
) -> dict[str, Any]:
    if not pdf_path:
        raise ValueError("Rob2Input requires pdf_path or pdf_bytes.")

    settings = get_settings()
    rules = get_locator_rules()

    top_k = _resolve_int(options.top_k, rules.defaults.top_k or _DEFAULT_TOP_K)
    per_query_top_n = _resolve_int(options.per_query_top_n, _DEFAULT_PER_QUERY_TOP_N)
    rrf_k = _resolve_int(options.rrf_k, _DEFAULT_RRF_K)
    use_structure = _resolve_bool(options.use_structure, False)
    locator_tokenizer = (
        _resolve_str(options.locator_tokenizer)
        or _resolve_str(settings.locator_tokenizer)
        or "auto"
    )
    locator_char_ngram = _resolve_int(
        options.locator_char_ngram, settings.locator_char_ngram or 2
    )

    relevance_mode = _resolve_choice(options.relevance_mode, "none")
    consistency_mode = _resolve_choice(options.consistency_mode, "none")

    relevance_min_confidence = _resolve_float(
        options.relevance_min_confidence, _DEFAULT_RELEVANCE_MIN_CONFIDENCE
    )
    consistency_min_confidence = _resolve_float(
        options.consistency_min_confidence, _DEFAULT_CONSISTENCY_MIN_CONFIDENCE
    )

    fusion_top_k = _resolve_int(options.fusion_top_k, top_k)
    fusion_rrf_k = _resolve_int(options.fusion_rrf_k, rrf_k)

    relevance_top_k = _resolve_int(options.relevance_top_k, top_k)
    relevance_top_n = _resolve_int(options.relevance_top_n, relevance_top_k)
    existence_top_k = _resolve_int(options.existence_top_k, top_k)
    validated_top_k = _resolve_int(options.validated_top_k, top_k)

    completeness_require_relevance = options.completeness_require_relevance
    if completeness_require_relevance is None:
        completeness_require_relevance = relevance_mode != "none"

    domain_evidence_top_k = _resolve_int(
        options.domain_evidence_top_k, _DEFAULT_DOMAIN_EVIDENCE_TOP_K
    )

    splade_model_id = _resolve_str(options.splade_model_id) or _resolve_str(settings.splade_model_id)
    if not splade_model_id:
        local_model = _local_splade_model()
        if local_model is not None:
            splade_model_id = str(local_model)
        else:
            splade_model_id = DEFAULT_SPLADE_MODEL_ID
            warnings.append("Using default SPLADE model id; set SPLADE_MODEL_ID to override.")

    reference_titles = options.preprocess_reference_titles
    if reference_titles is None:
        reference_titles = settings.preprocess_reference_titles

    return {
        "pdf_path": pdf_path,
        "docling_layout_model": _resolve_str(options.docling_layout_model)
        or _resolve_str(settings.docling_layout_model),
        "docling_artifacts_path": _resolve_str(options.docling_artifacts_path)
        or _resolve_str(settings.docling_artifacts_path),
        "docling_chunker_model": _resolve_str(options.docling_chunker_model)
        or _resolve_str(settings.docling_chunker_model),
        "docling_chunker_max_tokens": _resolve_optional_int(
            options.docling_chunker_max_tokens, settings.docling_chunker_max_tokens
        ),
        "preprocess_drop_references": _resolve_bool(
            options.preprocess_drop_references, settings.preprocess_drop_references
        ),
        "preprocess_reference_titles": reference_titles,
        "top_k": top_k,
        "per_query_top_n": per_query_top_n,
        "rrf_k": rrf_k,
        "query_planner": _resolve_choice(options.query_planner, "deterministic"),
        "query_planner_model": _resolve_str(options.query_planner_model) or _resolve_str(settings.query_planner_model),
        "query_planner_model_provider": _resolve_str(options.query_planner_model_provider)
        or _resolve_str(settings.query_planner_model_provider),
        "query_planner_temperature": _resolve_float(
            options.query_planner_temperature, settings.query_planner_temperature
        ),
        "query_planner_timeout": _resolve_optional_float(
            options.query_planner_timeout, settings.query_planner_timeout
        ),
        "query_planner_max_tokens": _resolve_optional_int(
            options.query_planner_max_tokens, settings.query_planner_max_tokens
        ),
        "query_planner_max_retries": _resolve_int(
            options.query_planner_max_retries, settings.query_planner_max_retries
        ),
        "query_planner_max_keywords": _resolve_int(
            options.query_planner_max_keywords, _DEFAULT_QUERY_PLANNER_MAX_KEYWORDS
        ),
        "reranker": _resolve_choice(options.reranker, "none"),
        "reranker_model_id": _resolve_str(options.reranker_model_id)
        or _resolve_str(settings.reranker_model_id)
        or DEFAULT_CROSS_ENCODER_MODEL_ID,
        "reranker_device": _resolve_str(options.reranker_device) or _resolve_str(settings.reranker_device),
        "reranker_max_length": _resolve_int(
            options.reranker_max_length, settings.reranker_max_length or _DEFAULT_RERANKER_MAX_LENGTH
        ),
        "reranker_batch_size": _resolve_int(
            options.reranker_batch_size, settings.reranker_batch_size or _DEFAULT_RERANKER_BATCH_SIZE
        ),
        "rerank_top_n": _resolve_int(
            options.rerank_top_n, settings.reranker_top_n or _DEFAULT_RERANKER_TOP_N
        ),
        "use_structure": use_structure,
        "section_bonus_weight": _resolve_float(
            options.section_bonus_weight, _DEFAULT_SECTION_BONUS_WEIGHT
        ),
        "locator_tokenizer": locator_tokenizer,
        "locator_char_ngram": locator_char_ngram,
        "splade_model_id": splade_model_id,
        "splade_device": _resolve_str(options.splade_device) or _resolve_str(settings.splade_device),
        "splade_hf_token": _resolve_str(options.splade_hf_token) or _resolve_str(settings.splade_hf_token),
        "splade_query_max_length": _resolve_int(
            options.splade_query_max_length, settings.splade_query_max_length or _DEFAULT_SPLADE_QUERY_MAX
        ),
        "splade_doc_max_length": _resolve_int(
            options.splade_doc_max_length, settings.splade_doc_max_length or _DEFAULT_SPLADE_DOC_MAX
        ),
        "splade_batch_size": _resolve_int(
            options.splade_batch_size, settings.splade_batch_size or _DEFAULT_SPLADE_BATCH
        ),
        "llm_locator_mode": _resolve_choice(
            options.llm_locator_mode, _resolve_choice(settings.llm_locator_mode, "llm")
        ),
        "llm_locator_model": _resolve_str(options.llm_locator_model)
        or _resolve_str(settings.llm_locator_model),
        "llm_locator_model_provider": _resolve_str(options.llm_locator_model_provider)
        or _resolve_str(settings.llm_locator_model_provider),
        "llm_locator_temperature": _resolve_float(
            options.llm_locator_temperature, settings.llm_locator_temperature
        ),
        "llm_locator_timeout": _resolve_optional_float(
            options.llm_locator_timeout, settings.llm_locator_timeout
        ),
        "llm_locator_max_tokens": _resolve_optional_int(
            options.llm_locator_max_tokens, settings.llm_locator_max_tokens
        ),
        "llm_locator_max_retries": _resolve_int(
            options.llm_locator_max_retries, settings.llm_locator_max_retries
        ),
        "llm_locator_max_steps": _resolve_int(
            options.llm_locator_max_steps,
            settings.llm_locator_max_steps or _DEFAULT_LLM_LOCATOR_MAX_STEPS,
        ),
        "llm_locator_seed_top_n": _resolve_int(
            options.llm_locator_seed_top_n,
            settings.llm_locator_seed_top_n or _DEFAULT_LLM_LOCATOR_SEED_TOP_N,
        ),
        "llm_locator_per_step_top_n": _resolve_int(
            options.llm_locator_per_step_top_n,
            settings.llm_locator_per_step_top_n or _DEFAULT_LLM_LOCATOR_PER_STEP_TOP_N,
        ),
        "llm_locator_max_candidates": _resolve_int(
            options.llm_locator_max_candidates,
            settings.llm_locator_max_candidates or _DEFAULT_LLM_LOCATOR_MAX_CANDIDATES,
        ),
        "fusion_top_k": fusion_top_k,
        "fusion_rrf_k": fusion_rrf_k,
        "fusion_engine_weights": options.fusion_engine_weights,
        "relevance_mode": relevance_mode,
        "relevance_model": _resolve_str(options.relevance_model) or _resolve_str(settings.relevance_model),
        "relevance_model_provider": _resolve_str(options.relevance_model_provider)
        or _resolve_str(settings.relevance_model_provider),
        "relevance_temperature": _resolve_float(
            options.relevance_temperature, settings.relevance_temperature
        ),
        "relevance_timeout": _resolve_optional_float(
            options.relevance_timeout, settings.relevance_timeout
        ),
        "relevance_max_tokens": _resolve_optional_int(
            options.relevance_max_tokens, settings.relevance_max_tokens
        ),
        "relevance_max_retries": _resolve_int(
            options.relevance_max_retries, settings.relevance_max_retries
        ),
        "relevance_min_confidence": relevance_min_confidence,
        "relevance_require_quote": _resolve_bool(options.relevance_require_quote, True),
        "relevance_fill_to_top_k": _resolve_bool(options.relevance_fill_to_top_k, True),
        "relevance_top_k": relevance_top_k,
        "relevance_top_n": relevance_top_n,
        "existence_require_text_match": _resolve_bool(options.existence_require_text_match, True),
        "existence_require_quote_in_source": _resolve_bool(options.existence_require_quote_in_source, True),
        "existence_top_k": existence_top_k,
        "consistency_mode": consistency_mode,
        "consistency_model": _resolve_str(options.consistency_model) or _resolve_str(settings.consistency_model),
        "consistency_model_provider": _resolve_str(options.consistency_model_provider)
        or _resolve_str(settings.consistency_model_provider),
        "consistency_temperature": _resolve_float(
            options.consistency_temperature, settings.consistency_temperature
        ),
        "consistency_timeout": _resolve_optional_float(
            options.consistency_timeout, settings.consistency_timeout
        ),
        "consistency_max_tokens": _resolve_optional_int(
            options.consistency_max_tokens, settings.consistency_max_tokens
        ),
        "consistency_max_retries": _resolve_int(
            options.consistency_max_retries, settings.consistency_max_retries
        ),
        "consistency_min_confidence": consistency_min_confidence,
        "consistency_require_quotes_for_fail": _resolve_bool(
            options.consistency_require_quotes_for_fail, True
        ),
        "consistency_top_n": _resolve_int(options.consistency_top_n, _DEFAULT_CONSISTENCY_TOP_N),
        "completeness_enforce": _resolve_bool(options.completeness_enforce, False),
        "completeness_required_questions": options.completeness_required_questions,
        "completeness_min_passed_per_question": _resolve_int(
            options.completeness_min_passed_per_question, 1
        ),
        "completeness_require_relevance": completeness_require_relevance,
        "validated_top_k": validated_top_k,
        "validation_max_retries": _resolve_int(options.validation_max_retries, _DEFAULT_MAX_RETRIES),
        "validation_fail_on_consistency": _resolve_bool(
            options.validation_fail_on_consistency, True
        ),
        "validation_relax_on_retry": _resolve_bool(options.validation_relax_on_retry, True),
        "d2_effect_type": _resolve_choice(options.d2_effect_type, "assignment"),
        "domain_evidence_top_k": domain_evidence_top_k,
        "d1_model": _resolve_str(options.d1_model) or _resolve_str(settings.d1_model),
        "d1_model_provider": _resolve_str(options.d1_model_provider)
        or _resolve_str(settings.d1_model_provider),
        "d1_temperature": _resolve_float(options.d1_temperature, settings.d1_temperature),
        "d1_timeout": _resolve_optional_float(options.d1_timeout, settings.d1_timeout),
        "d1_max_tokens": _resolve_optional_int(options.d1_max_tokens, settings.d1_max_tokens),
        "d1_max_retries": _resolve_int(options.d1_max_retries, settings.d1_max_retries or _DEFAULT_DOMAIN_MAX_RETRIES),
        "d2_model": _resolve_str(options.d2_model) or _resolve_str(settings.d2_model),
        "d2_model_provider": _resolve_str(options.d2_model_provider)
        or _resolve_str(settings.d2_model_provider),
        "d2_temperature": _resolve_float(options.d2_temperature, settings.d2_temperature),
        "d2_timeout": _resolve_optional_float(options.d2_timeout, settings.d2_timeout),
        "d2_max_tokens": _resolve_optional_int(options.d2_max_tokens, settings.d2_max_tokens),
        "d2_max_retries": _resolve_int(options.d2_max_retries, settings.d2_max_retries or _DEFAULT_DOMAIN_MAX_RETRIES),
        "d3_model": _resolve_str(options.d3_model) or _resolve_str(settings.d3_model),
        "d3_model_provider": _resolve_str(options.d3_model_provider)
        or _resolve_str(settings.d3_model_provider),
        "d3_temperature": _resolve_float(options.d3_temperature, settings.d3_temperature),
        "d3_timeout": _resolve_optional_float(options.d3_timeout, settings.d3_timeout),
        "d3_max_tokens": _resolve_optional_int(options.d3_max_tokens, settings.d3_max_tokens),
        "d3_max_retries": _resolve_int(options.d3_max_retries, settings.d3_max_retries or _DEFAULT_DOMAIN_MAX_RETRIES),
        "d4_model": _resolve_str(options.d4_model) or _resolve_str(settings.d4_model),
        "d4_model_provider": _resolve_str(options.d4_model_provider)
        or _resolve_str(settings.d4_model_provider),
        "d4_temperature": _resolve_float(options.d4_temperature, settings.d4_temperature),
        "d4_timeout": _resolve_optional_float(options.d4_timeout, settings.d4_timeout),
        "d4_max_tokens": _resolve_optional_int(options.d4_max_tokens, settings.d4_max_tokens),
        "d4_max_retries": _resolve_int(options.d4_max_retries, settings.d4_max_retries or _DEFAULT_DOMAIN_MAX_RETRIES),
        "d5_model": _resolve_str(options.d5_model) or _resolve_str(settings.d5_model),
        "d5_model_provider": _resolve_str(options.d5_model_provider)
        or _resolve_str(settings.d5_model_provider),
        "d5_temperature": _resolve_float(options.d5_temperature, settings.d5_temperature),
        "d5_timeout": _resolve_optional_float(options.d5_timeout, settings.d5_timeout),
        "d5_max_tokens": _resolve_optional_int(options.d5_max_tokens, settings.d5_max_tokens),
        "d5_max_retries": _resolve_int(options.d5_max_retries, settings.d5_max_retries or _DEFAULT_DOMAIN_MAX_RETRIES),
        "domain_audit_mode": _resolve_choice(options.domain_audit_mode, "none"),
        "domain_audit_model": _resolve_str(options.domain_audit_model)
        or _resolve_str(settings.domain_audit_model)
        or _resolve_str(settings.d1_model),
        "domain_audit_model_provider": _resolve_str(options.domain_audit_model_provider)
        or _resolve_str(settings.domain_audit_model_provider),
        "domain_audit_temperature": _resolve_float(
            options.domain_audit_temperature, settings.domain_audit_temperature
        ),
        "domain_audit_timeout": _resolve_optional_float(
            options.domain_audit_timeout, settings.domain_audit_timeout
        ),
        "domain_audit_max_tokens": _resolve_optional_int(
            options.domain_audit_max_tokens, settings.domain_audit_max_tokens
        ),
        "domain_audit_max_retries": _resolve_int(
            options.domain_audit_max_retries, settings.domain_audit_max_retries or _DEFAULT_DOMAIN_MAX_RETRIES
        ),
        "domain_audit_patch_window": _resolve_int(
            options.domain_audit_patch_window, settings.domain_audit_patch_window or _DEFAULT_AUDIT_PATCH_WINDOW
        ),
        "domain_audit_max_patches_per_question": _resolve_int(
            options.domain_audit_max_patches_per_question,
            settings.domain_audit_max_patches_per_question or _DEFAULT_AUDIT_MAX_PATCHES,
        ),
        "domain_audit_rerun_domains": _resolve_bool(
            options.domain_audit_rerun_domains,
            settings.domain_audit_rerun_domains if settings.domain_audit_rerun_domains is not None else True,
        ),
        "domain_audit_final": _resolve_bool(
            options.domain_audit_final, settings.domain_audit_final
        ),
    }


def _build_result(
    final_state: Mapping[str, Any],
    options: Rob2RunOptions,
    runtime_ms: int,
    warnings: list[str],
) -> Rob2RunResult:
    raw_output = final_state.get("rob2_result") or {}
    result = Rob2FinalOutput.model_validate(raw_output)
    table_markdown = str(final_state.get("rob2_table_markdown") or "")

    resolved_audit_mode = str(final_state.get("domain_audit_mode") or options.domain_audit_mode or "none").strip().lower()
    include_audit = options.include_audit_reports
    if include_audit is None:
        include_audit = resolved_audit_mode == "llm"

    include_reports = options.include_reports
    if include_reports is None:
        include_reports = _resolve_choice(options.debug_level, "none") != "none"

    debug_level = _resolve_choice(options.debug_level, "none")
    debug_payload = _build_debug_payload(final_state, debug_level)

    reports = _collect_reports(final_state) if include_reports else None
    audit_reports = final_state.get("domain_audit_reports") if include_audit else None

    return Rob2RunResult(
        result=result,
        table_markdown=table_markdown,
        reports=reports,
        audit_reports=audit_reports,
        debug=debug_payload,
        runtime_ms=runtime_ms,
        warnings=warnings,
    )


def _collect_reports(state: Mapping[str, Any]) -> dict[str, Any]:
    report_keys = [
        "llm_locator_debug",
        "relevance_validator",
        "relevance_config",
        "relevance_debug",
        "consistency_validator",
        "consistency_config",
        "consistency_reports",
        "completeness_report",
        "completeness_config",
        "existence_config",
        "existence_debug",
        "validation_retry_log",
    ]
    return {key: state.get(key) for key in report_keys if key in state}


def _build_debug_payload(state: Mapping[str, Any], level: str) -> dict[str, Any] | None:
    if level == "none":
        return None
    if level == "full":
        return {"state": dict(state)}
    keys = [
        "validation_attempt",
        "validation_retry_log",
        "retry_question_ids",
        "fulltext_fallback_used",
        "llm_locator_debug",
        "completeness_passed",
        "completeness_failed_questions",
        "consistency_failed_questions",
        "domain_audit_reports",
        "relevance_config",
        "consistency_config",
        "completeness_config",
    ]
    return {"state": {key: state.get(key) for key in keys if key in state}}


def _resolve_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _resolve_choice(value: Any, default: str) -> str:
    if value is None:
        return default
    return str(value).strip().lower() or default


def _resolve_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _resolve_int(value: Any, default: int) -> int:
    if value is None:
        return int(default)
    return int(str(value))


def _resolve_optional_int(value: Any, default: int | None) -> int | None:
    if value is None:
        return int(default) if default is not None else None
    return int(str(value))


def _resolve_float(value: Any, default: float) -> float:
    if value is None:
        return float(default)
    return float(str(value))


def _resolve_optional_float(value: Any, default: float | None) -> float | None:
    if value is None:
        return float(default) if default is not None else None
    return float(str(value))


def _local_splade_model() -> Path | None:
    repo_root = Path(__file__).resolve().parents[2]
    candidate = repo_root / "models" / "splade_distil_CoCodenser_large"
    return candidate if candidate.exists() else None


__all__ = ["run_rob2"]
