"""Application configuration and .env loading."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Centralized runtime configuration."""

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
