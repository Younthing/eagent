"""Domain reasoning output schemas."""

from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from schemas.internal.locator import DomainId

AnswerOption = Literal["Y", "PY", "PN", "N", "NI", "NA"]
DomainRisk = Literal["low", "some_concerns", "high"]


class EvidenceRef(BaseModel):
    """Evidence reference attached to a domain answer."""

    paragraph_id: str
    page: Optional[int] = None
    title: Optional[str] = None
    quote: Optional[str] = None

    model_config = ConfigDict(extra="forbid")


class DomainAnswer(BaseModel):
    """Answer to a single ROB2 signaling question."""

    question_id: str
    answer: AnswerOption
    rationale: str
    evidence_refs: List[EvidenceRef] = Field(default_factory=list)
    confidence: Optional[float] = Field(default=None, ge=0, le=1)

    model_config = ConfigDict(extra="forbid")


class DomainDecision(BaseModel):
    """Domain-level decision summary."""

    domain: DomainId
    effect_type: Optional[Literal["assignment", "adherence"]] = None
    risk: DomainRisk
    risk_rationale: str
    answers: List[DomainAnswer]
    missing_questions: List[str] = Field(default_factory=list)
    rule_trace: List[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


__all__ = [
    "AnswerOption",
    "DomainAnswer",
    "DomainDecision",
    "DomainRisk",
    "EvidenceRef",
]
