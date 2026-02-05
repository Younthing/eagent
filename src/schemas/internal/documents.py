"""Document structure contracts for preprocessing output."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from schemas.internal.metadata import DocumentMetadata


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
    pages: Optional[List[int]] = None
    bbox: Optional[BoundingBox] = None
    bboxes: Optional[List[BoundingBox]] = None
    bboxes_by_page: Optional[dict[str, List[BoundingBox]]] = None
    doc_item_ids: Optional[List[str]] = None
    text: str


class DocStructure(BaseModel):
    """Normalized structure emitted by the preprocessing layer."""

    body: str
    sections: List[SectionSpan]
    docling_config: Optional[dict[str, object]] = Field(
        default=None,
        description="Docling preprocessing configuration metadata.",
    )
    document_metadata: Optional[DocumentMetadata] = None

    model_config = ConfigDict(extra="allow")


__all__ = ["BoundingBox", "SectionSpan", "DocStructure"]
