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
