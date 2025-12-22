"""Shared contracts for rerankers.

Rerankers are optional second-stage components that re-score retrieved candidates
given a (query, passage) pair. They must be deterministic when configured with a
fixed model and parameters (temperature-free).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence


@dataclass(frozen=True)
class RerankResult:
    """Scores aligned to the input passages, plus best-first ordering indices."""

    scores: list[float]
    order: list[int]


class Reranker(Protocol):
    """Reranker interface shared by cross-encoder and (future) LLM rerankers."""

    name: str

    def rerank(
        self,
        query: str,
        passages: Sequence[str],
        *,
        max_length: int = 512,
        batch_size: int = 8,
    ) -> RerankResult: ...


__all__ = ["RerankResult", "Reranker"]

