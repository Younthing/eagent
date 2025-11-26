"""LLM factory helpers."""

from functools import lru_cache

from langchain.chat_models import init_chat_model

from eagent.config import settings


@lru_cache(maxsize=1)
def get_default_llm():
    """Return a LangChain chat model honoring provider:model syntax."""
    return init_chat_model(
        model=settings.default_model,
        temperature=settings.default_temperature,
    )
