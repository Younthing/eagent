"""External request schemas for ROB2 runs."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Rob2Input(BaseModel):
    pdf_path: str | None = None
    pdf_bytes: bytes | None = None
    filename: str | None = None

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def _validate_source(self) -> "Rob2Input":
        if bool(self.pdf_path) == bool(self.pdf_bytes):
            raise ValueError("Provide exactly one of pdf_path or pdf_bytes.")
        return self


class Rob2RunOptions(BaseModel):
    """Per-run overrides. All fields are optional and validated."""

    # Preprocessing (Docling)
    docling_layout_model: str | None = None
    docling_artifacts_path: str | None = None
    docling_chunker_model: str | None = None
    docling_chunker_max_tokens: int | None = Field(default=None, ge=1)
    preprocess_drop_references: bool | None = None
    preprocess_reference_titles: list[str] | str | None = None

    # Retrieval + fusion
    top_k: int | None = Field(default=None, ge=1)
    per_query_top_n: int | None = Field(default=None, ge=1)
    rrf_k: int | None = Field(default=None, ge=1)
    query_planner: Literal["deterministic", "llm"] | None = None
    query_planner_model: str | None = None
    query_planner_model_provider: str | None = None
    query_planner_temperature: float | None = None
    query_planner_timeout: float | None = None
    query_planner_max_tokens: int | None = Field(default=None, ge=1)
    query_planner_max_retries: int | None = Field(default=None, ge=0)
    query_planner_max_keywords: int | None = Field(default=None, ge=1)

    reranker: Literal["none", "cross_encoder"] | None = None
    reranker_model_id: str | None = None
    reranker_device: str | None = None
    reranker_max_length: int | None = Field(default=None, ge=1)
    reranker_batch_size: int | None = Field(default=None, ge=1)
    rerank_top_n: int | None = Field(default=None, ge=1)

    use_structure: bool | None = None
    section_bonus_weight: float | None = Field(default=None, ge=0)
    locator_tokenizer: Literal[
        "auto",
        "english",
        "pkuseg_medicine",
        "pkuseg",
        "jieba",
        "char",
    ] | None = None
    locator_char_ngram: int | None = Field(default=None, ge=1)

    splade_model_id: str | None = None
    splade_device: str | None = None
    splade_hf_token: str | None = None
    splade_query_max_length: int | None = Field(default=None, ge=1)
    splade_doc_max_length: int | None = Field(default=None, ge=1)
    splade_batch_size: int | None = Field(default=None, ge=1)

    fusion_top_k: int | None = Field(default=None, ge=1)
    fusion_rrf_k: int | None = Field(default=None, ge=1)
    fusion_engine_weights: dict[str, float] | None = None

    # Validators
    relevance_mode: Literal["none", "llm"] | None = None
    relevance_model: str | None = None
    relevance_model_provider: str | None = None
    relevance_temperature: float | None = None
    relevance_timeout: float | None = None
    relevance_max_tokens: int | None = Field(default=None, ge=1)
    relevance_max_retries: int | None = Field(default=None, ge=0)
    relevance_min_confidence: float | None = Field(default=None, ge=0, le=1)
    relevance_require_quote: bool | None = None
    relevance_fill_to_top_k: bool | None = None
    relevance_top_k: int | None = Field(default=None, ge=1)
    relevance_top_n: int | None = Field(default=None, ge=1)

    existence_require_text_match: bool | None = None
    existence_require_quote_in_source: bool | None = None
    existence_top_k: int | None = Field(default=None, ge=1)

    consistency_mode: Literal["none", "llm"] | None = None
    consistency_model: str | None = None
    consistency_model_provider: str | None = None
    consistency_temperature: float | None = None
    consistency_timeout: float | None = None
    consistency_max_tokens: int | None = Field(default=None, ge=1)
    consistency_max_retries: int | None = Field(default=None, ge=0)
    consistency_min_confidence: float | None = Field(default=None, ge=0, le=1)
    consistency_require_quotes_for_fail: bool | None = None
    consistency_top_n: int | None = Field(default=None, ge=2)

    completeness_enforce: bool | None = None
    completeness_required_questions: list[str] | None = None
    completeness_min_passed_per_question: int | None = Field(default=None, ge=1)
    completeness_require_relevance: bool | None = None
    validated_top_k: int | None = Field(default=None, ge=1)

    validation_max_retries: int | None = Field(default=None, ge=0)
    validation_fail_on_consistency: bool | None = None
    validation_relax_on_retry: bool | None = None

    # Domain reasoning
    d2_effect_type: Literal["assignment", "adherence"] | None = None
    domain_evidence_top_k: int | None = Field(default=None, ge=1)

    d1_model: str | None = None
    d1_model_provider: str | None = None
    d1_temperature: float | None = None
    d1_timeout: float | None = None
    d1_max_tokens: int | None = Field(default=None, ge=1)
    d1_max_retries: int | None = Field(default=None, ge=0)

    d2_model: str | None = None
    d2_model_provider: str | None = None
    d2_temperature: float | None = None
    d2_timeout: float | None = None
    d2_max_tokens: int | None = Field(default=None, ge=1)
    d2_max_retries: int | None = Field(default=None, ge=0)

    d3_model: str | None = None
    d3_model_provider: str | None = None
    d3_temperature: float | None = None
    d3_timeout: float | None = None
    d3_max_tokens: int | None = Field(default=None, ge=1)
    d3_max_retries: int | None = Field(default=None, ge=0)

    d4_model: str | None = None
    d4_model_provider: str | None = None
    d4_temperature: float | None = None
    d4_timeout: float | None = None
    d4_max_tokens: int | None = Field(default=None, ge=1)
    d4_max_retries: int | None = Field(default=None, ge=0)

    d5_model: str | None = None
    d5_model_provider: str | None = None
    d5_temperature: float | None = None
    d5_timeout: float | None = None
    d5_max_tokens: int | None = Field(default=None, ge=1)
    d5_max_retries: int | None = Field(default=None, ge=0)

    # Domain audit
    domain_audit_mode: Literal["none", "llm"] | None = None
    domain_audit_model: str | None = None
    domain_audit_model_provider: str | None = None
    domain_audit_temperature: float | None = None
    domain_audit_timeout: float | None = None
    domain_audit_max_tokens: int | None = Field(default=None, ge=1)
    domain_audit_max_retries: int | None = Field(default=None, ge=0)
    domain_audit_patch_window: int | None = Field(default=None, ge=0)
    domain_audit_max_patches_per_question: int | None = Field(default=None, ge=1)
    domain_audit_rerun_domains: bool | None = None
    domain_audit_final: bool | None = None

    # Output controls
    debug_level: Literal["none", "min", "full"] | None = None
    include_reports: bool | None = None
    include_audit_reports: bool | None = None

    model_config = ConfigDict(extra="forbid")


__all__ = ["Rob2Input", "Rob2RunOptions"]
