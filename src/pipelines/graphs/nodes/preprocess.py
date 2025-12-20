"""Docling-driven preprocessing node."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterable, List, Optional

from schemas.internal.documents import BoundingBox, DocStructure, SectionSpan
from utils.text import normalize_block

try:  # optional dependency
    from langchain_docling import DoclingLoader
except Exception:  # pragma: no cover
    DoclingLoader = None

logger = logging.getLogger(__name__)


def preprocess_node(state: dict) -> dict:
    """LangGraph node: parse PDF into a normalized document structure."""

    source = state.get("pdf_path") or state.get("source") or state.get("file_path")
    if not source:
        raise ValueError("preprocess_node requires 'pdf_path' or 'source'.")

    doc_structure = parse_docling_pdf(source)
    return {"doc_structure": doc_structure.model_dump()}


def parse_docling_pdf(source: str | Path) -> DocStructure:
    """Parse a PDF into DocStructure using Docling metadata."""

    path = Path(str(source))
    spans: List[SectionSpan] = []
    body_text = ""

    if path.exists() and DoclingLoader is not None:
        spans, body_text = _load_with_docling(path)

    if not body_text:
        body_text = _read_plain_text(path) if path.exists() else str(source)
        body_text = normalize_block(body_text)

    if not spans and body_text:
        spans = [
            SectionSpan(
                paragraph_id="p0-0001",
                title="body",
                page=None,
                bbox=None,
                text=body_text,
            )
        ]

    section_map = _aggregate_sections_by_title(spans)
    payload = {"body": body_text, "sections": spans, "spans": spans, **section_map}
    return DocStructure.model_validate(payload)


def _load_with_docling(path: Path) -> tuple[List[SectionSpan], str]:
    """Load content with Docling and extract metadata-driven spans."""

    try:
        loader = DoclingLoader(file_path=str(path))
        documents = loader.load()
        spans = _documents_to_spans(documents)
        body = normalize_block("\n\n".join(span.text for span in spans))
        return spans, body
    except Exception as exc:  # pragma: no cover
        logger.warning("Docling parsing failed, falling back to plain text: %s", exc)
        return [], ""


def _documents_to_spans(documents: Iterable[object]) -> List[SectionSpan]:
    spans: List[SectionSpan] = []

    for index, doc in enumerate(documents, start=1):
        raw_text = getattr(doc, "page_content", "") or ""
        normalized_text = normalize_block(raw_text)
        if not normalized_text:
            continue

        meta = getattr(doc, "metadata", {}) or {}
        dl_meta = meta.get("dl_meta") or {}
        title = _coalesce_heading(dl_meta.get("headings")) or "body"
        page, bbox = _get_first_page_and_bbox(dl_meta)
        paragraph_id = _get_paragraph_id(dl_meta, index, page)

        spans.append(
            SectionSpan(
                paragraph_id=paragraph_id,
                title=title,
                page=page,
                bbox=bbox,
                text=normalized_text,
            )
        )

    return spans


def _coalesce_heading(headings: object) -> str:
    if isinstance(headings, str):
        return headings.strip()

    if isinstance(headings, Iterable) and not isinstance(headings, (bytes, bytearray)):
        parts = [str(item).strip() for item in headings if str(item).strip()]
        if parts:
            return " > ".join(parts)

    return ""


def _get_first_page_and_bbox(dl_meta: object) -> tuple[Optional[int], Optional[BoundingBox]]:
    if not isinstance(dl_meta, dict):
        return None, None

    doc_items = dl_meta.get("doc_items") or []
    for item in doc_items:
        if not isinstance(item, dict):
            continue
        prov = item.get("prov") or []
        for entry in prov:
            if not isinstance(entry, dict):
                continue
            page_no = entry.get("page_no")
            bbox = _bbox_from_raw(entry.get("bbox"))
            return page_no, bbox

    return None, None


def _bbox_from_raw(raw_bbox: object) -> Optional[BoundingBox]:
    if not isinstance(raw_bbox, dict):
        return None

    try:
        return BoundingBox(
            left=float(raw_bbox["l"]),
            top=float(raw_bbox["t"]),
            right=float(raw_bbox["r"]),
            bottom=float(raw_bbox["b"]),
            origin=str(raw_bbox.get("coord_origin"))
            if raw_bbox.get("coord_origin")
            else None,
        )
    except Exception:
        return None


def _get_paragraph_id(
    dl_meta: object, index: int, page: Optional[int]
) -> str:
    if isinstance(dl_meta, dict):
        doc_items = dl_meta.get("doc_items") or []
        for item in doc_items:
            if not isinstance(item, dict):
                continue
            item_id = item.get("id") or item.get("element_id")
            if item_id:
                return str(item_id)

    page_tag = str(page) if page is not None else "na"
    return f"p{page_tag}-{index:04d}"


def _aggregate_sections_by_title(spans: Iterable[SectionSpan]) -> dict[str, str]:
    aggregated: dict[str, List[str]] = {}
    for span in spans:
        title = span.title.strip() if isinstance(span.title, str) else ""
        text = span.text.strip() if isinstance(span.text, str) else ""
        if not title or title.lower() == "body" or not text:
            continue
        aggregated.setdefault(title, []).append(text)

    return {title: "\n\n".join(parts) for title, parts in aggregated.items()}


def _read_plain_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except FileNotFoundError:
        logger.warning("File not found: %s", path)
    except Exception as exc:  # pragma: no cover
        logger.warning("Failed to read file: %s", exc)
    return ""


__all__ = ["parse_docling_pdf", "preprocess_node"]
