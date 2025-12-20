"""Document structure contracts for preprocessing output."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class BoundingBox(BaseModel):
    """Bounding box coordinates from Docling provenance."""

    left: float
    top: float
    right: float
    bottom: float
    origin: Optional[str] = None


class SectionSpan(BaseModel):
    """A paragraph-level span with section context."""

    paragraph_id: str = Field(description="Stable paragraph identifier.")
    title: str = Field(description="Section heading path.")
    page: Optional[int] = None
    bbox: Optional[BoundingBox] = None
    text: str


class DocStructure(BaseModel):
    """Normalized structure emitted by the preprocessing layer."""

    body: str
    sections: List[SectionSpan]

    model_config = ConfigDict(extra="allow")


__all__ = ["BoundingBox", "SectionSpan", "DocStructure"]
