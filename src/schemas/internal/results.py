"""Final ROB2 output contracts (Milestone 10)."""

from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from schemas.internal.decisions import AnswerOption, DomainRisk, EvidenceRef
from schemas.internal.locator import DomainId
from schemas.internal.metadata import DocumentMetadata

OverallRisk = Literal["low", "some_concerns", "high", "not_applicable"]


class CitationUse(BaseModel):
    domain: DomainId
    question_id: str
    quote: Optional[str] = None

    model_config = ConfigDict(extra="forbid")


class Citation(BaseModel):
    paragraph_id: str
    page: Optional[int] = None
    title: Optional[str] = None
    text: Optional[str] = None
    uses: List[CitationUse] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class Rob2AnswerResult(BaseModel):
    question_id: str
    rob2_id: Optional[str] = None
    text: Optional[str] = None
    answer: AnswerOption
    rationale: str
    evidence_refs: List[EvidenceRef] = Field(default_factory=list)
    confidence: Optional[float] = Field(default=None, ge=0, le=1)

    model_config = ConfigDict(extra="forbid")


class Rob2DomainResult(BaseModel):
    domain: DomainId
    effect_type: Optional[Literal["assignment", "adherence"]] = None
    risk: DomainRisk
    risk_rationale: str
    answers: List[Rob2AnswerResult]
    missing_questions: List[str] = Field(default_factory=list)
    rule_trace: List[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class Rob2OverallResult(BaseModel):
    risk: OverallRisk
    rationale: str

    model_config = ConfigDict(extra="forbid")


class Rob2FinalOutput(BaseModel):
    variant: Literal["standard"] = "standard"
    question_set_version: str
    overall: Rob2OverallResult
    domains: List[Rob2DomainResult]
    citations: List[Citation] = Field(default_factory=list)
    document_metadata: Optional[DocumentMetadata] = None

    model_config = ConfigDict(extra="forbid")


__all__ = [
    "Citation",
    "CitationUse",
    "OverallRisk",
    "Rob2AnswerResult",
    "Rob2DomainResult",
    "Rob2FinalOutput",
    "Rob2OverallResult",
]
