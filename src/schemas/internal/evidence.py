"""Evidence contracts emitted by locator layers."""

from __future__ import annotations

from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class EvidenceSupport(BaseModel):
    """A single engine's support for a fused evidence candidate."""

    engine: str
    rank: int = Field(ge=1)
    score: float = Field(ge=0)
    query: Optional[str] = None

    model_config = ConfigDict(extra="forbid")


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
    supporting_quote: Optional[str] = None

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


class RelevanceVerdict(BaseModel):
    """Relevance judgement for a candidate paragraph (Milestone 7)."""

    label: Literal["relevant", "irrelevant", "unknown"]
    confidence: Optional[float] = Field(default=None, ge=0, le=1)
    supporting_quote: Optional[str] = None

    model_config = ConfigDict(extra="forbid")


class ExistenceVerdict(BaseModel):
    """Existence judgement for a candidate paragraph (Milestone 7)."""

    label: Literal["pass", "fail"]
    reason: Optional[str] = None
    paragraph_id_found: bool
    text_match: Optional[bool] = None
    quote_found: Optional[bool] = None

    model_config = ConfigDict(extra="forbid")


class ConsistencyConflict(BaseModel):
    """A conflicting pair of paragraphs for the same question (Milestone 7)."""

    paragraph_id_a: str
    paragraph_id_b: str
    reason: Optional[str] = None
    quote_a: Optional[str] = None
    quote_b: Optional[str] = None

    model_config = ConfigDict(extra="forbid")


class ConsistencyVerdict(BaseModel):
    """Consistency judgement across multiple evidence candidates (Milestone 7)."""

    label: Literal["pass", "fail", "unknown"]
    confidence: Optional[float] = Field(default=None, ge=0, le=1)
    conflicts: List[ConsistencyConflict] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class CompletenessItem(BaseModel):
    """Completeness status for a single signaling question (Milestone 7)."""

    question_id: str
    required: bool
    passed_count: int = Field(ge=0)
    status: Literal["satisfied", "missing"]

    model_config = ConfigDict(extra="forbid")


class FusedEvidenceCandidate(BaseModel):
    """A merged evidence candidate with multi-engine supports (Milestone 6).

    Optional validator annotations (Milestone 7) live on the candidate to
    support debug-first pipelines without proliferating wrapper schemas.
    """

    question_id: str
    paragraph_id: str
    title: str
    page: Optional[int] = None
    text: str

    fusion_score: float = Field(ge=0)
    fusion_rank: int = Field(ge=1)
    support_count: int = Field(ge=1)
    supports: List[EvidenceSupport]

    relevance: Optional[RelevanceVerdict] = None
    existence: Optional[ExistenceVerdict] = None

    model_config = ConfigDict(extra="forbid")


class FusedEvidenceBundle(BaseModel):
    """Top-k fused evidence bundle for a question."""

    question_id: str
    items: List[FusedEvidenceCandidate]

    model_config = ConfigDict(extra="forbid")


__all__ = [
    "CompletenessItem",
    "ConsistencyConflict",
    "ConsistencyVerdict",
    "EvidenceBundle",
    "EvidenceCandidate",
    "ExistenceVerdict",
    "EvidenceSupport",
    "FusedEvidenceBundle",
    "FusedEvidenceCandidate",
    "RelevanceVerdict",
]
