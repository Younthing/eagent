"""Application settings configuration."""

from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central settings object loaded from environment/.env."""

    # Default agent generation parameters
    default_model: str = Field(default="openai:gpt-4o")
    default_temperature: float = Field(default=0.0)

    # LangSmith / tracing hints
    langsmith_tracing: bool = Field(default=False)
    langsmith_project: str = Field(default="literature-agent")
    langsmith_endpoint: Optional[str] = Field(default=None)
    langsmith_api_key: Optional[str] = Field(default=None)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
