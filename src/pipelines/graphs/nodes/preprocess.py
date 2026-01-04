"""Docling-driven preprocessing node with langchain_docling plugin."""

from __future__ import annotations

import logging
from hashlib import sha1
from urllib.parse import urlparse
from pathlib import Path
from typing import Any, Iterable, List, Optional, TYPE_CHECKING, cast

from core.config import get_settings
from langchain_docling.loader import DoclingLoader
from schemas.internal.documents import BoundingBox, DocStructure, SectionSpan
from utils.text import normalize_block

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from docling.datamodel.layout_model_specs import LayoutModelConfig
    from docling.document_converter import DocumentConverter
    from docling_core.transforms.chunker.base import BaseChunker
    from langchain_core.documents import Document

_CONVERTER_CACHE: tuple[Optional["DocumentConverter"], dict[str, object]] | None = None
_CHUNKER_CACHE: tuple[Optional["BaseChunker"], dict[str, object]] | None = None


def preprocess_node(state: dict) -> dict:
    """LangGraph node: parse PDF into a normalized document structure."""
    pdf_path = state.get("pdf_path")
    if not pdf_path:
        raise ValueError("preprocess_node requires 'pdf_path'.")

    overrides = _read_docling_overrides(state)
    doc_structure = parse_docling_pdf(pdf_path, overrides=overrides)
    return {"doc_structure": doc_structure.model_dump()}


def parse_docling_pdf(
    source: str | Path,
    *,
    overrides: Optional[dict[str, object]] = None,
) -> DocStructure:
    """Parse a PDF into DocStructure using Docling metadata."""
    resolved_source = _resolve_docling_source(source)
    spans, body_text, docling_config = _load_with_docling(
        resolved_source,
        overrides=overrides,
    )

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


def _load_with_docling(
    source: str,
    *,
    overrides: Optional[dict[str, object]] = None,
) -> tuple[List[SectionSpan], str, dict[str, object]]:
    """Load content with Docling via LangChain DoclingLoader."""
    try:
        converter, config = _build_docling_converter(overrides=overrides)
        chunker, chunker_config = _build_docling_chunker(overrides=overrides)
        config = {**config, **chunker_config}
        loader = DoclingLoader(
            file_path=source,
            converter=converter,
            chunker=chunker,
        )
        documents = loader.load()
        if not documents:
            raise ValueError("Docling returned no documents.")
        spans = _documents_to_spans(documents)
        if not spans:
            raise ValueError("Docling returned no spans.")
        body = normalize_block("\n\n".join(span.text for span in spans))
        if not body:
            raise ValueError("Docling returned empty body text.")
        logger.debug("Docling parsed %d spans from %s", len(spans), source)
        return spans, body, config
    except Exception as exc:
        logger.warning("Docling parsing failed for %s", source, exc_info=True)
        raise RuntimeError(f"Docling parsing failed for {source}") from exc


def _build_docling_converter(
    *,
    overrides: Optional[dict[str, object]] = None,
) -> tuple[Optional["DocumentConverter"], dict[str, object]]:
    """Build a Docling converter with explicit, configurable model settings.

    Environment:
        DOCLING_LAYOUT_MODEL: layout model name (e.g., docling_layout_heron).
        DOCLING_ARTIFACTS_PATH: local model artifacts directory.
    """
    global _CONVERTER_CACHE
    if overrides is None and _CONVERTER_CACHE is not None:
        return _CONVERTER_CACHE

    try:
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions
        from docling.document_converter import DocumentConverter, PdfFormatOption
    except Exception:
        return None, {}

    settings = get_settings()
    config: dict[str, object] = {"pipeline": "standard_pdf"}
    artifacts_path = settings.docling_artifacts_path
    layout_model_name = settings.docling_layout_model
    if overrides:
        if overrides.get("docling_artifacts_path") is not None:
            artifacts_path = str(overrides["docling_artifacts_path"])
        if overrides.get("docling_layout_model") is not None:
            layout_model_name = str(overrides["docling_layout_model"])

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
    if overrides is None:
        _CONVERTER_CACHE = (converter, config)
        return _CONVERTER_CACHE
    return converter, config


def _build_docling_chunker(
    *,
    overrides: Optional[dict[str, object]] = None,
) -> tuple[Optional["BaseChunker"], dict[str, object]]:
    """Build HybridChunker with configurable tokenizer and max tokens."""
    global _CHUNKER_CACHE
    if overrides is None and _CHUNKER_CACHE is not None:
        return _CHUNKER_CACHE

    try:
        from docling_core.transforms.chunker.hybrid_chunker import HybridChunker
        from docling_core.transforms.chunker.tokenizer.huggingface import (
            HuggingFaceTokenizer,
        )
        from transformers import AutoTokenizer
    except Exception as exc:
        raise RuntimeError(
            "HybridChunker dependencies missing. Install docling-core[chunking]."
        ) from exc

    settings = get_settings()
    model_id = settings.docling_chunker_model or "sentence-transformers/all-MiniLM-L6-v2"
    max_tokens = settings.docling_chunker_max_tokens
    if overrides:
        if overrides.get("docling_chunker_model") is not None:
            model_id = str(overrides["docling_chunker_model"])
        if overrides.get("docling_chunker_max_tokens") is not None:
            max_tokens = int(overrides["docling_chunker_max_tokens"])

    raw_tokenizer = AutoTokenizer.from_pretrained(model_id)
    if max_tokens is None:
        tokenizer = HuggingFaceTokenizer(tokenizer=raw_tokenizer)
    else:
        tokenizer = HuggingFaceTokenizer(
            tokenizer=raw_tokenizer,
            max_tokens=max_tokens,
        )
    chunker = HybridChunker(tokenizer=tokenizer)
    config: dict[str, object] = {
        "chunker": "hybrid",
        "chunker_model": model_id,
        "chunker_max_tokens": max_tokens,
    }
    if overrides is None:
        _CHUNKER_CACHE = (chunker, config)
        return _CHUNKER_CACHE
    return chunker, config


def _read_docling_overrides(state: dict) -> Optional[dict[str, object]]:
    keys = (
        "docling_layout_model",
        "docling_artifacts_path",
        "docling_chunker_model",
        "docling_chunker_max_tokens",
    )
    overrides = {key: state.get(key) for key in keys if state.get(key) is not None}
    return overrides or None


def _resolve_layout_model(name: Optional[str]) -> Optional["LayoutModelConfig"]:
    """Resolve a Docling layout model config from a name string."""
    if not name:
        return None
    try:
        from docling.datamodel import layout_model_specs
        from docling.datamodel.layout_model_specs import LayoutModelConfig
    except Exception:
        return None

    normalized = name.strip().lower()

    for attr in dir(layout_model_specs):
        value = getattr(layout_model_specs, attr)
        if isinstance(value, LayoutModelConfig):
            if value.name.lower() == normalized:
                return value
    return None


def _resolve_docling_source(source: str | Path) -> str:
    """Validate and normalize PDF sources for Docling."""
    source_str = str(source)
    if _is_url(source_str):
        return source_str

    path = Path(source_str)
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {path}")
    if not path.is_file():
        raise ValueError(f"Expected a PDF file, got: {path}")
    if path.suffix.lower() != ".pdf":
        raise ValueError(f"Expected a PDF file, got: {path.name}")
    return str(path)


def _is_url(source: str) -> bool:
    """Return True when the source is an HTTP(S) URL."""
    parsed = urlparse(source)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _documents_to_spans(documents: Iterable["Document"]) -> List[SectionSpan]:
    """Convert LangChain Documents to SectionSpan with rich metadata."""
    spans: List[SectionSpan] = []

    for index, doc in enumerate(documents, start=1):
        raw_text = doc.page_content if hasattr(doc, "page_content") else ""
        normalized_text = normalize_block(raw_text)
        if not normalized_text:
            continue

        # 核心：提取Docling的结构化metadata（不受插件影响）
        meta = getattr(doc, "metadata", {}) or {}
        if not isinstance(meta, dict):
            meta = {}
        dl_meta = meta.get("dl_meta") or {}
        if not isinstance(dl_meta, dict):
            dl_meta = {}

        title = _coalesce_heading(dl_meta.get("headings")) or "body"
        doc_item_ids = _get_doc_item_ids(dl_meta)
        pages, bboxes_by_page = _get_pages_and_bboxes(dl_meta)
        bboxes_by_page_payload = {
            str(page_no): boxes for page_no, boxes in bboxes_by_page.items()
        }
        page = pages[0] if pages else None
        bboxes = bboxes_by_page.get(page, []) if page is not None else []
        bbox = _union_bboxes(bboxes) if bboxes else None
        paragraph_id = _get_paragraph_id(doc_item_ids, index, page)

        spans.append(
            SectionSpan(
                paragraph_id=paragraph_id,
                title=title,
                page=page,
                pages=pages or None,
                bbox=bbox,
                bboxes=bboxes or None,
                bboxes_by_page=bboxes_by_page_payload or None,
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


def _get_pages_and_bboxes(
    dl_meta: dict[str, Any],
) -> tuple[List[int], dict[int, List[BoundingBox]]]:
    """Extract page numbers and bounding boxes from doc_items."""
    doc_items = dl_meta.get("doc_items") or []
    bboxes_by_page: dict[int, List[BoundingBox]] = {}
    for item in doc_items:
        if not isinstance(item, dict):
            continue
        prov = item.get("prov") or []
        for entry in prov:
            if not isinstance(entry, dict):
                continue
            page_no = entry.get("page_no")
            if not isinstance(page_no, int):
                continue
            bbox = _bbox_from_raw(entry.get("bbox"))
            if bbox is None or page_no is None:
                continue
            bboxes_by_page.setdefault(page_no, []).append(bbox)

    pages = sorted(bboxes_by_page.keys())
    return pages, bboxes_by_page


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

    raw_bbox = cast(dict[str, Any], raw_bbox)
    try:
        left = raw_bbox.get("l")
        top = raw_bbox.get("t")
        right = raw_bbox.get("r")
        bottom = raw_bbox.get("b")
        if not isinstance(left, (int, float, str)):
            raise TypeError("Invalid bbox value types.")
        if not isinstance(top, (int, float, str)):
            raise TypeError("Invalid bbox value types.")
        if not isinstance(right, (int, float, str)):
            raise TypeError("Invalid bbox value types.")
        if not isinstance(bottom, (int, float, str)):
            raise TypeError("Invalid bbox value types.")
        origin = raw_bbox.get("coord_origin")
        return BoundingBox(
            left=float(left),
            top=float(top),
            right=float(right),
            bottom=float(bottom),
            origin=str(origin) if origin else None,
        )
    except (KeyError, ValueError, TypeError):
        logger.debug("Invalid bbox format: %s", raw_bbox)
        return None


def _get_doc_item_ids(dl_meta: dict[str, Any]) -> Optional[List[str]]:
    """Collect doc_item ids for strong paragraph backtrace."""
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

    return sorted(ids) or None


def _get_paragraph_id(
    doc_item_ids: Optional[List[str]],
    index: int,
    page: Optional[int],
) -> str:
    """Generate stable paragraph ID from Docling metadata or fallback."""
    if doc_item_ids:
        digest = sha1("|".join(doc_item_ids).encode("utf-8")).hexdigest()[:12]
        return f"dl-{digest}"

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


__all__ = ["parse_docling_pdf", "preprocess_node"]
