"""Application configuration and .env loading."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Centralized runtime configuration."""

    persistence_enabled: bool = Field(
        default=True, validation_alias="PERSISTENCE_ENABLED"
    )
    persistence_dir: str = Field(
        default="data/rob2", validation_alias="PERSISTENCE_DIR"
    )
    persistence_scope: str = Field(
        default="analysis", validation_alias="PERSISTENCE_SCOPE"
    )
    cache_dir: str = Field(
        default="data/rob2", validation_alias="CACHE_DIR"
    )
    cache_scope: str = Field(
        default="deterministic", validation_alias="CACHE_SCOPE"
    )

    docling_layout_model: str | None = Field(
        default=None, validation_alias="DOCLING_LAYOUT_MODEL"
    )
    docling_artifacts_path: str | None = Field(
        default=None, validation_alias="DOCLING_ARTIFACTS_PATH"
    )
    docling_chunker_model: str | None = Field(
        default=None, validation_alias="DOCLING_CHUNKER_MODEL"
    )
    docling_chunker_max_tokens: int | None = Field(
        default=None, validation_alias="DOCLING_CHUNKER_MAX_TOKENS"
    )
    preprocess_drop_references: bool = Field(
        default=True, validation_alias="PREPROCESS_DROP_REFERENCES"
    )
    preprocess_reference_titles: str | None = Field(
        default=None, validation_alias="PREPROCESS_REFERENCE_TITLES"
    )
    doc_scope_mode: str = Field(
        default="auto", validation_alias="DOC_SCOPE_MODE"
    )
    doc_scope_include_paragraph_ids: str | None = Field(
        default=None, validation_alias="DOC_SCOPE_INCLUDE_PARAGRAPH_IDS"
    )
    doc_scope_page_range: str | None = Field(
        default=None, validation_alias="DOC_SCOPE_PAGE_RANGE"
    )
    doc_scope_min_pages: int = Field(
        default=6, validation_alias="DOC_SCOPE_MIN_PAGES"
    )
    doc_scope_min_confidence: float = Field(
        default=0.75, validation_alias="DOC_SCOPE_MIN_CONFIDENCE"
    )
    doc_scope_abstract_gap_pages: int = Field(
        default=3, validation_alias="DOC_SCOPE_ABSTRACT_GAP_PAGES"
    )
    prompt_lang: str = Field(default="zh", validation_alias="PROMPT_LANG")
    locator_tokenizer: str = Field(
        default="auto", validation_alias="LOCATOR_TOKENIZER"
    )
    locator_char_ngram: int = Field(
        default=2, validation_alias="LOCATOR_CHAR_NGRAM"
    )

    query_planner_model: str | None = Field(
        default=None, validation_alias="QUERY_PLANNER_MODEL"
    )
    query_planner_model_provider: str | None = Field(
        default=None, validation_alias="QUERY_PLANNER_MODEL_PROVIDER"
    )
    query_planner_temperature: float = Field(
        default=0.0, validation_alias="QUERY_PLANNER_TEMPERATURE"
    )
    query_planner_timeout: float | None = Field(
        default=None, validation_alias="QUERY_PLANNER_TIMEOUT"
    )
    query_planner_max_tokens: int | None = Field(
        default=None, validation_alias="QUERY_PLANNER_MAX_TOKENS"
    )
    query_planner_max_retries: int = Field(
        default=2, validation_alias="QUERY_PLANNER_MAX_RETRIES"
    )

    reranker_model_id: str | None = Field(
        default=None, validation_alias="RERANKER_MODEL_ID"
    )
    reranker_device: str | None = Field(default=None, validation_alias="RERANKER_DEVICE")
    reranker_max_length: int = Field(default=512, validation_alias="RERANKER_MAX_LENGTH")
    reranker_batch_size: int = Field(default=8, validation_alias="RERANKER_BATCH_SIZE")
    reranker_top_n: int = Field(default=50, validation_alias="RERANKER_TOP_N")

    splade_model_id: str | None = Field(
        default=None, validation_alias="SPLADE_MODEL_ID"
    )
    splade_device: str | None = Field(
        default=None, validation_alias="SPLADE_DEVICE"
    )
    splade_hf_token: str | None = Field(
        default=None, validation_alias="SPLADE_HF_TOKEN"
    )
    splade_query_max_length: int = Field(
        default=64, validation_alias="SPLADE_QUERY_MAX_LENGTH"
    )
    splade_doc_max_length: int = Field(
        default=256, validation_alias="SPLADE_DOC_MAX_LENGTH"
    )
    splade_batch_size: int = Field(
        default=8, validation_alias="SPLADE_BATCH_SIZE"
    )

    llm_locator_mode: str = Field(
        default="none", validation_alias="LLM_LOCATOR_MODE"
    )
    llm_locator_model: str | None = Field(
        default=None, validation_alias="LLM_LOCATOR_MODEL"
    )
    llm_locator_model_provider: str | None = Field(
        default=None, validation_alias="LLM_LOCATOR_MODEL_PROVIDER"
    )
    llm_locator_temperature: float = Field(
        default=0.0, validation_alias="LLM_LOCATOR_TEMPERATURE"
    )
    llm_locator_timeout: float | None = Field(
        default=None, validation_alias="LLM_LOCATOR_TIMEOUT"
    )
    llm_locator_max_tokens: int | None = Field(
        default=None, validation_alias="LLM_LOCATOR_MAX_TOKENS"
    )
    llm_locator_max_retries: int = Field(
        default=2, validation_alias="LLM_LOCATOR_MAX_RETRIES"
    )
    llm_locator_max_steps: int = Field(
        default=3, validation_alias="LLM_LOCATOR_MAX_STEPS"
    )
    llm_locator_seed_top_n: int = Field(
        default=5, validation_alias="LLM_LOCATOR_SEED_TOP_N"
    )
    llm_locator_per_step_top_n: int = Field(
        default=10, validation_alias="LLM_LOCATOR_PER_STEP_TOP_N"
    )
    llm_locator_max_candidates: int = Field(
        default=40, validation_alias="LLM_LOCATOR_MAX_CANDIDATES"
    )

    relevance_model: str | None = Field(default=None, validation_alias="RELEVANCE_MODEL")
    relevance_model_provider: str | None = Field(
        default=None, validation_alias="RELEVANCE_MODEL_PROVIDER"
    )
    relevance_temperature: float = Field(
        default=0.0, validation_alias="RELEVANCE_TEMPERATURE"
    )
    relevance_timeout: float | None = Field(
        default=None, validation_alias="RELEVANCE_TIMEOUT"
    )
    relevance_max_tokens: int | None = Field(
        default=None, validation_alias="RELEVANCE_MAX_TOKENS"
    )
    relevance_max_retries: int = Field(
        default=2, validation_alias="RELEVANCE_MAX_RETRIES"
    )

    consistency_model: str | None = Field(
        default=None, validation_alias="CONSISTENCY_MODEL"
    )
    consistency_model_provider: str | None = Field(
        default=None, validation_alias="CONSISTENCY_MODEL_PROVIDER"
    )
    consistency_temperature: float = Field(
        default=0.0, validation_alias="CONSISTENCY_TEMPERATURE"
    )
    consistency_timeout: float | None = Field(
        default=None, validation_alias="CONSISTENCY_TIMEOUT"
    )
    consistency_max_tokens: int | None = Field(
        default=None, validation_alias="CONSISTENCY_MAX_TOKENS"
    )
    consistency_max_retries: int = Field(
        default=2, validation_alias="CONSISTENCY_MAX_RETRIES"
    )

    d1_model: str | None = Field(default=None, validation_alias="D1_MODEL")
    d1_model_provider: str | None = Field(
        default=None, validation_alias="D1_MODEL_PROVIDER"
    )
    d1_temperature: float = Field(default=0.0, validation_alias="D1_TEMPERATURE")
    d1_timeout: float | None = Field(default=None, validation_alias="D1_TIMEOUT")
    d1_max_tokens: int | None = Field(default=None, validation_alias="D1_MAX_TOKENS")
    d1_max_retries: int = Field(default=2, validation_alias="D1_MAX_RETRIES")

    d2_model: str | None = Field(default=None, validation_alias="D2_MODEL")
    d2_model_provider: str | None = Field(
        default=None, validation_alias="D2_MODEL_PROVIDER"
    )
    d2_temperature: float = Field(default=0.0, validation_alias="D2_TEMPERATURE")
    d2_timeout: float | None = Field(default=None, validation_alias="D2_TIMEOUT")
    d2_max_tokens: int | None = Field(default=None, validation_alias="D2_MAX_TOKENS")
    d2_max_retries: int = Field(default=2, validation_alias="D2_MAX_RETRIES")

    d3_model: str | None = Field(default=None, validation_alias="D3_MODEL")
    d3_model_provider: str | None = Field(
        default=None, validation_alias="D3_MODEL_PROVIDER"
    )
    d3_temperature: float = Field(default=0.0, validation_alias="D3_TEMPERATURE")
    d3_timeout: float | None = Field(default=None, validation_alias="D3_TIMEOUT")
    d3_max_tokens: int | None = Field(default=None, validation_alias="D3_MAX_TOKENS")
    d3_max_retries: int = Field(default=2, validation_alias="D3_MAX_RETRIES")

    d4_model: str | None = Field(default=None, validation_alias="D4_MODEL")
    d4_model_provider: str | None = Field(
        default=None, validation_alias="D4_MODEL_PROVIDER"
    )
    d4_temperature: float = Field(default=0.0, validation_alias="D4_TEMPERATURE")
    d4_timeout: float | None = Field(default=None, validation_alias="D4_TIMEOUT")
    d4_max_tokens: int | None = Field(default=None, validation_alias="D4_MAX_TOKENS")
    d4_max_retries: int = Field(default=2, validation_alias="D4_MAX_RETRIES")

    d5_model: str | None = Field(default=None, validation_alias="D5_MODEL")
    d5_model_provider: str | None = Field(
        default=None, validation_alias="D5_MODEL_PROVIDER"
    )
    d5_temperature: float = Field(default=0.0, validation_alias="D5_TEMPERATURE")
    d5_timeout: float | None = Field(default=None, validation_alias="D5_TIMEOUT")
    d5_max_tokens: int | None = Field(default=None, validation_alias="D5_MAX_TOKENS")
    d5_max_retries: int = Field(default=2, validation_alias="D5_MAX_RETRIES")

    domain_audit_mode: str = Field(default="llm", validation_alias="DOMAIN_AUDIT_MODE")
    domain_audit_model: str | None = Field(
        default=None, validation_alias="DOMAIN_AUDIT_MODEL"
    )
    domain_audit_model_provider: str | None = Field(
        default=None, validation_alias="DOMAIN_AUDIT_MODEL_PROVIDER"
    )
    domain_audit_temperature: float = Field(
        default=0.0, validation_alias="DOMAIN_AUDIT_TEMPERATURE"
    )
    domain_audit_timeout: float | None = Field(
        default=None, validation_alias="DOMAIN_AUDIT_TIMEOUT"
    )
    domain_audit_max_tokens: int | None = Field(
        default=None, validation_alias="DOMAIN_AUDIT_MAX_TOKENS"
    )
    domain_audit_max_retries: int = Field(
        default=2, validation_alias="DOMAIN_AUDIT_MAX_RETRIES"
    )
    domain_audit_patch_window: int = Field(
        default=0, validation_alias="DOMAIN_AUDIT_PATCH_WINDOW"
    )
    domain_audit_max_patches_per_question: int = Field(
        default=3, validation_alias="DOMAIN_AUDIT_MAX_PATCHES_PER_QUESTION"
    )
    domain_audit_rerun_domains: bool = Field(
        default=True, validation_alias="DOMAIN_AUDIT_RERUN_DOMAINS"
    )
    domain_audit_final: bool = Field(
        default=False, validation_alias="DOMAIN_AUDIT_FINAL"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Load settings once from .env/environment."""
    return Settings()


__all__ = ["Settings", "get_settings"]
