"""Telemetry helpers for LangSmith instrumentation."""

import os
from functools import lru_cache
from typing import Any, Callable, TypeVar

from langsmith import traceable

from eagent.config import settings

FuncT = TypeVar("FuncT", bound=Callable[..., Any])


@lru_cache(maxsize=1)
def configure_langsmith_env() -> None:
    """Ensure LangSmith env vars follow values loaded via settings."""

    if settings.langsmith_project:
        os.environ.setdefault("LANGSMITH_PROJECT", settings.langsmith_project)
    if settings.langsmith_endpoint:
        os.environ.setdefault("LANGSMITH_ENDPOINT", settings.langsmith_endpoint)
    if settings.langsmith_api_key:
        os.environ.setdefault("LANGSMITH_API_KEY", settings.langsmith_api_key)

    if settings.langsmith_tracing:
        os.environ.setdefault("LANGSMITH_TRACING", "true")


def traceable_if_enabled(*decorator_args, **decorator_kwargs):
    """Wrap LangSmith traceable decorator, honoring configuration."""

    configure_langsmith_env()
    langsmith_enabled = settings.langsmith_tracing

    def decorator(func: FuncT) -> FuncT:
        if not langsmith_enabled:
            return func
        wrapped = traceable(*decorator_args, **decorator_kwargs)(func)
        return wrapped  # type: ignore[return-value]

    return decorator
