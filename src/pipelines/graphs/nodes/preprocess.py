"""Docling-driven preprocessing node with langchain_docling plugin."""

from __future__ import annotations

import logging
import os
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
    source = (
        state.get("pdf_path")
        or state.get("source")
        or state.get("file_path")
    )
    if not source:
        raise ValueError("preprocess_node requires 'pdf_path' or 'source'.")

    doc_structure = parse_docling_pdf(source)
    return {"doc_structure": doc_structure.model_dump()}


def parse_docling_pdf(source: str | Path) -> DocStructure:
    """Parse a PDF into DocStructure using Docling metadata."""
    path = Path(str(source))
    spans: List[SectionSpan] = []
    body_text = ""
    docling_config: dict[str, object] = {}

    if path.exists() and DoclingLoader is not None:
        spans, body_text, docling_config = _load_with_docling(path)

    # Fallback for plain text (no structure)
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
    payload = {
        "body": body_text,
        "sections": spans,
        "spans": spans,
        **section_map,
    }
    if docling_config:
        payload["docling_config"] = docling_config
    return DocStructure.model_validate(payload)


def _load_with_docling(path: Path) -> tuple[List[SectionSpan], str, dict[str, object]]:
    """Load content with Docling via LangChain DoclingLoader."""
    try:
        converter, config = _build_docling_converter()
        loader_kwargs = {"file_path": str(path)}
        if converter is not None:
            loader_kwargs["converter"] = converter
        loader = DoclingLoader(**loader_kwargs)
        documents = loader.load()
        spans = _documents_to_spans(documents)
        body = normalize_block("\n\n".join(span.text for span in spans))
        logger.debug("Docling parsed %d spans from %s", len(spans), path.name)
        return spans, body, config
    except Exception as exc:
        logger.warning("Docling parsing failed for %s: %s", path, exc)
        return [], "", {}


def _build_docling_converter() -> tuple[Optional[object], dict[str, object]]:
    """Build a Docling converter with explicit, configurable model settings.

    Environment:
        DOCLING_LAYOUT_MODEL: layout model name (e.g., docling_layout_heron).
        DOCLING_ARTIFACTS_PATH: local model artifacts directory.
    """
    try:
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions
        from docling.document_converter import DocumentConverter, PdfFormatOption
    except Exception:
        return None, {}

    config: dict[str, object] = {"pipeline": "standard_pdf"}
    artifacts_path = os.getenv("DOCLING_ARTIFACTS_PATH")
    layout_model_name = os.getenv("DOCLING_LAYOUT_MODEL")

    pipeline_options = PdfPipelineOptions()
    if artifacts_path:
        pipeline_options.artifacts_path = artifacts_path
        config["artifacts_path"] = artifacts_path

    resolved_layout = _resolve_layout_model(layout_model_name)
    if layout_model_name and resolved_layout is None:
        logger.warning("Unknown DOCLING_LAYOUT_MODEL: %s", layout_model_name)
    if resolved_layout is not None:
        pipeline_options.layout_options.model_spec = resolved_layout

    layout_spec = pipeline_options.layout_options.model_spec
    if layout_spec is not None:
        config["layout_model"] = getattr(layout_spec, "name", None)
        config["layout_repo_id"] = getattr(layout_spec, "repo_id", None)

    try:
        import docling  # type: ignore

        config["docling_version"] = getattr(docling, "__version__", "unknown")
    except Exception:
        pass

    converter = DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
        }
    )
    return converter, config


def _resolve_layout_model(name: Optional[str]) -> Optional[object]:
    """Resolve a Docling layout model config from a name string."""
    if not name:
        return None
    try:
        from docling.datamodel import layout_model_specs
    except Exception:
        return None

    normalized = name.strip().lower()
    layout_config_type = getattr(layout_model_specs, "LayoutModelConfig", None)
    if layout_config_type is None:
        return None

    for attr in dir(layout_model_specs):
        value = getattr(layout_model_specs, attr)
        if isinstance(value, layout_config_type):
            if getattr(value, "name", "").lower() == normalized:
                return value
    return None


def _documents_to_spans(documents: Iterable[object]) -> List[SectionSpan]:
    """Convert LangChain Documents to SectionSpan with rich metadata."""
    spans: List[SectionSpan] = []

    for index, doc in enumerate(documents, start=1):
        # ✅ 插件启用后直接可用page_content
        raw_text = doc.page_content if hasattr(doc, "page_content") else ""
        normalized_text = normalize_block(raw_text)
        if not normalized_text:
            continue

        # 核心：提取Docling的结构化metadata（不受插件影响）
        meta = getattr(doc, "metadata", {}) or {}
        dl_meta = meta.get("dl_meta") or {}
        
        title = _coalesce_heading(dl_meta.get("headings")) or "body"
        page, bbox, bboxes = _get_page_and_bboxes(dl_meta)
        paragraph_id = _get_paragraph_id(dl_meta, index, page)
        doc_item_ids = _get_doc_item_ids(dl_meta)

        spans.append(
            SectionSpan(
                paragraph_id=paragraph_id,
                title=title,
                page=page,
                bbox=bbox,
                bboxes=bboxes,
                doc_item_ids=doc_item_ids,
                text=normalized_text,
            )
        )

    return spans


def _coalesce_heading(headings: object) -> str:
    """Extract and coalesce headings from Docling metadata."""
    if isinstance(headings, str):
        return headings.strip()

    if isinstance(headings, Iterable) and not isinstance(headings, (bytes, bytearray)):
        parts = [str(item).strip() for item in headings if str(item).strip()]
        if parts:
            return " > ".join(parts)

    return ""


def _get_page_and_bboxes(
    dl_meta: object,
) -> tuple[Optional[int], Optional[BoundingBox], Optional[List[BoundingBox]]]:
    """Extract page number and bounding boxes from doc_items."""
    if not isinstance(dl_meta, dict):
        return None, None, None

    doc_items = dl_meta.get("doc_items") or []
    page = None
    bboxes: List[BoundingBox] = []
    for item in doc_items:
        if not isinstance(item, dict):
            continue
        prov = item.get("prov") or []
        for entry in prov:
            if not isinstance(entry, dict):
                continue
            page_no = entry.get("page_no")
            bbox = _bbox_from_raw(entry.get("bbox"))
            if bbox is None:
                continue
            if page is None and page_no is not None:
                page = page_no
            if page_no == page:
                bboxes.append(bbox)

    union_bbox = _union_bboxes(bboxes) if bboxes else None
    return page, union_bbox, bboxes or None


def _union_bboxes(bboxes: Iterable[BoundingBox]) -> Optional[BoundingBox]:
    """Compute a bounding box that covers all provided boxes."""
    boxes = list(bboxes)
    if not boxes:
        return None
    left = min(box.left for box in boxes)
    top = min(box.top for box in boxes)
    right = max(box.right for box in boxes)
    bottom = max(box.bottom for box in boxes)
    origin = boxes[0].origin if boxes[0].origin else None
    return BoundingBox(
        left=left,
        top=top,
        right=right,
        bottom=bottom,
        origin=origin,
    )


def _bbox_from_raw(raw_bbox: object) -> Optional[BoundingBox]:
    """Parse raw bounding box dict to BoundingBox model."""
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
    except (KeyError, ValueError, TypeError):
        logger.debug("Invalid bbox format: %s", raw_bbox)
        return None


def _get_doc_item_ids(dl_meta: object) -> Optional[List[str]]:
    """Collect doc_item ids for strong paragraph backtrace."""
    if not isinstance(dl_meta, dict):
        return None

    doc_items = dl_meta.get("doc_items") or []
    ids: List[str] = []
    seen: set[str] = set()
    for item in doc_items:
        if not isinstance(item, dict):
            continue
        item_id = item.get("id") or item.get("element_id")
        if not item_id:
            continue
        item_id = str(item_id)
        if item_id not in seen:
            seen.add(item_id)
            ids.append(item_id)

    return ids or None


def _get_paragraph_id(dl_meta: object, index: int, page: Optional[int]) -> str:
    """Generate stable paragraph ID from Docling metadata or fallback."""
    if isinstance(dl_meta, dict):
        doc_items = dl_meta.get("doc_items") or []
        for item in doc_items:
            if isinstance(item, dict):
                item_id = item.get("id") or item.get("element_id")
                if item_id:
                    return str(item_id)

    # Fallback: page-based ID
    page_tag = str(page) if page is not None else "na"
    return f"p{page_tag}-{index:04d}"


def _aggregate_sections_by_title(spans: Iterable[SectionSpan]) -> dict[str, str]:
    """Group spans by title for section-based access."""
    aggregated: dict[str, List[str]] = {}
    for span in spans:
        title = span.title.strip() if isinstance(span.title, str) else ""
        text = span.text.strip() if isinstance(span.text, str) else ""
        if not title or title.lower() == "body" or not text:
            continue
        aggregated.setdefault(title, []).append(text)

    return {title: "\n\n".join(parts) for title, parts in aggregated.items()}


def _read_plain_text(path: Path) -> str:
    """Fallback plain text reader."""
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except FileNotFoundError:
        logger.warning("File not found: %s", path)
        return ""
    except Exception as exc:
        logger.warning("Failed to read plain text from %s: %s", path, exc)
        return ""


__all__ = ["parse_docling_pdf", "preprocess_node"]
