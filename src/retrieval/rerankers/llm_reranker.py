"""LLM reranker placeholder (future milestone).

Intentionally left unimplemented: the current system uses deterministic retrieval
and (optional) local cross-encoder reranking first.
"""

from __future__ import annotations

from typing import Sequence

from retrieval.rerankers.contracts import RerankResult


class LLMReranker:
    name = "llm"

    def rerank(
        self,
        query: str,
        passages: Sequence[str],
        *,
        max_length: int = 512,
        batch_size: int = 8,
    ) -> RerankResult:
        raise NotImplementedError("LLM reranker is not implemented yet.")


__all__ = ["LLMReranker"]

