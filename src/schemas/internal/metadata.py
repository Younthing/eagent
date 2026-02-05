"""Document metadata extraction schemas."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class DocumentMetadataSource(BaseModel):
    paragraph_id: str
    quote: str

    model_config = ConfigDict(extra="forbid")


class DocumentMetadataExtraction(BaseModel):
    method: str
    model_id: Optional[str] = None
    provider: Optional[str] = None
    confidence: Optional[float] = Field(default=None, ge=0, le=1)
    error: Optional[str] = None

    model_config = ConfigDict(extra="forbid")


class DocumentMetadata(BaseModel):
    title: Optional[str] = None
    authors: List[str] = Field(default_factory=list)
    year: Optional[int] = None
    affiliations: List[str] = Field(default_factory=list)
    funders: List[str] = Field(default_factory=list)
    sources: List[DocumentMetadataSource] = Field(default_factory=list)
    extraction: Optional[DocumentMetadataExtraction] = None

    model_config = ConfigDict(extra="forbid")


__all__ = [
    "DocumentMetadata",
    "DocumentMetadataExtraction",
    "DocumentMetadataSource",
]
