"""Evidence contracts emitted by locator layers."""

from __future__ import annotations

from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class EvidenceCandidate(BaseModel):
    """A paragraph-level evidence candidate for a specific question."""

    question_id: str
    paragraph_id: str
    title: str
    page: Optional[int] = None
    text: str

    source: Literal["rule_based", "retrieval", "fulltext"]
    score: float = Field(ge=0)

    engine: Optional[str] = None
    engine_score: Optional[float] = Field(default=None, ge=0)

    query: Optional[str] = None
    bm25_score: Optional[float] = Field(default=None, ge=0)
    rrf_score: Optional[float] = Field(default=None, ge=0)
    retrieval_rank: Optional[int] = Field(default=None, ge=1)
    query_ranks: Optional[Dict[str, int]] = None
    reranker: Optional[str] = None
    rerank_score: Optional[float] = Field(default=None, ge=0)
    rerank_rank: Optional[int] = Field(default=None, ge=1)

    section_score: Optional[float] = Field(default=None, ge=0)
    keyword_score: Optional[float] = Field(default=None, ge=0)
    matched_keywords: Optional[List[str]] = None
    matched_section_priors: Optional[List[str]] = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("matched_keywords", "matched_section_priors")
    @classmethod
    def _empty_lists_to_none(
        cls, value: Optional[List[str]]
    ) -> Optional[List[str]]:
        if value is None:
            return None
        return value or None


class EvidenceBundle(BaseModel):
    """Top-k evidence bundle for a question."""

    question_id: str
    items: List[EvidenceCandidate]

    model_config = ConfigDict(extra="forbid")


__all__ = ["EvidenceCandidate", "EvidenceBundle"]
