"""Locator configuration schemas."""

from __future__ import annotations

from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

DomainId = Literal["D1", "D2", "D3", "D4", "D5"]


class LocatorDefaults(BaseModel):
    """Defaults applied across locator implementations."""

    top_k: int = Field(default=5, ge=1, le=50)

    model_config = ConfigDict(extra="forbid")


class DomainLocatorRule(BaseModel):
    """Rule-based hints per domain."""

    section_priors: List[str] = Field(default_factory=list)
    keywords: List[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class QuestionLocatorOverride(BaseModel):
    """Rule overrides for a specific question_id."""

    section_priors: Optional[List[str]] = None
    keywords: Optional[List[str]] = None

    model_config = ConfigDict(extra="forbid")


class LocatorRules(BaseModel):
    """Root config object for locator rules."""

    version: str
    variant: Literal["standard"]
    defaults: LocatorDefaults = Field(default_factory=LocatorDefaults)
    domains: Dict[DomainId, DomainLocatorRule]
    question_overrides: Dict[str, QuestionLocatorOverride] = Field(
        default_factory=dict
    )

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def _validate_domains(self) -> "LocatorRules":
        missing = {domain for domain in ("D1", "D2", "D3", "D4", "D5") if domain not in self.domains}
        if missing:
            raise ValueError(f"Missing domain rules: {sorted(missing)}")
        return self


__all__ = [
    "DomainId",
    "DomainLocatorRule",
    "LocatorDefaults",
    "LocatorRules",
    "QuestionLocatorOverride",
]

