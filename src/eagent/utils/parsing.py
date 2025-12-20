"""Docling 驱动的文档解析工具。

示例:
    result = parse_pdf_structure("paper.pdf")
    # result["sections"][0] 可能类似:
    # {'title': '3.2 AI 模型', 'page': 3, 'bbox': {'left': 108.0, 'top': 405.14, 'right': 504.0, 'bottom': 330.78, 'origin': 'BOTTOMLEFT'}, 'text': '...'}
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple, TypedDict

from eagent.telemetry import traceable_if_enabled

try:  # pragma: no cover - optional dependency
    from langchain_docling import DoclingLoader
except Exception:  # pragma: no cover
    DoclingLoader = None

MAX_FALLBACK_CHARS = 4000
logger = logging.getLogger(__name__)


class BoundingBox(TypedDict):
    left: float
    top: float
    right: float
    bottom: float
    origin: Optional[str]


class SectionSpan(TypedDict):
    title: str
    page: Optional[int]
    bbox: Optional[BoundingBox]
    text: str


@traceable_if_enabled(run_type="parser", name="Docling Parser")
def parse_pdf_structure(source: str | Path) -> Dict[str, object]:
    """使用 Docling 将文件解析为标准结构。

    Args:
        source: 文档路径或原始文本。优先尝试当作文件解析。

    Returns:
        Dict[str, object]: 包含全文 `body`，以及按标题聚合的章节文本和带元数据的 `sections`。

    Raises:
        FileNotFoundError: 当传入路径不存在时会记录警告并退回原始字符串。
    """

    path = Path(str(source))
    text = ""
    sections: List[SectionSpan] = []

    if DoclingLoader and path.exists():
        sections, text = _load_with_docling(path)

    if not text:
        text = _read_plain_text(path) if path.exists() else str(source)

    normalized = _normalize_block(text)
    if len(normalized) > MAX_FALLBACK_CHARS:
        normalized = normalized[:MAX_FALLBACK_CHARS]

    doc_structure: Dict[str, object] = {
        "body": normalized,
        "sections": sections,
    }

    for title, content in _aggregate_sections_by_title(sections).items():
        doc_structure[title] = content

    return doc_structure


def _load_with_docling(path: Path) -> Tuple[List[SectionSpan], str]:
    """通过 DoclingLoader 加载、拼接文本，并捕获章节元数据。"""

    try:
        loader = DoclingLoader(file_path=str(path))
        documents = loader.load()
        sections = _documents_to_sections(documents)
        body = "\n\n".join(section["text"] for section in sections).strip()
        return sections, body
    except Exception as exc:  # pragma: no cover - 记录错误即可
        logger.warning("Docling 解析失败，将尝试纯文本读取: %s", exc)
        return [], ""


def _documents_to_sections(documents: Sequence[object]) -> List[SectionSpan]:
    sections: List[SectionSpan] = []

    for doc in documents:
        raw_text = getattr(doc, "page_content", "") or ""
        normalized_text = _normalize_block(raw_text)
        if not normalized_text:
            continue

        meta = getattr(doc, "metadata", {}) or {}
        dl_meta = meta.get("dl_meta") or {}
        title = _coalesce_heading(dl_meta.get("headings"))
        page, bbox = _get_first_page_and_bbox(dl_meta)

        sections.append(
            {
                "title": title or "body",
                "page": page,
                "bbox": bbox,
                "text": normalized_text,
            }
        )

    return sections


def _coalesce_heading(headings: object) -> str:
    if isinstance(headings, str):
        return headings.strip()

    if isinstance(headings, Sequence) and not isinstance(headings, (bytes, bytearray)):
        normalized = [str(h).strip() for h in headings if str(h).strip()]
        if normalized:
            return " > ".join(normalized)

    return ""


def _get_first_page_and_bbox(dl_meta: object) -> Tuple[Optional[int], Optional[BoundingBox]]:
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
        return {
            "left": float(raw_bbox["l"]),
            "top": float(raw_bbox["t"]),
            "right": float(raw_bbox["r"]),
            "bottom": float(raw_bbox["b"]),
            "origin": str(raw_bbox.get("coord_origin")) if raw_bbox.get("coord_origin") else None,
        }
    except Exception:
        return None


def _aggregate_sections_by_title(sections: Sequence[SectionSpan]) -> Dict[str, str]:
    aggregated: Dict[str, List[str]] = {}
    for section in sections:
        title = section.get("title") or ""
        text = section.get("text") or ""
        if not title or title.lower() == "body" or not text:
            continue
        aggregated.setdefault(title, []).append(text)

    return {
        title: "\n\n".join(parts)
        for title, parts in aggregated.items()
    }


def _read_plain_text(path: Path) -> str:
    """读取本地文件，读取失败则返回空字符串。"""

    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except FileNotFoundError:
        logger.warning("未找到文件: %s", path)
    except Exception as exc:  # pragma: no cover
        logger.warning("读取文件失败: %s", exc)
    return ""


def _normalize_block(text: str) -> str:
    """清理换行和多余空格。"""

    cleaned = text.replace("\r\n", "\n").replace("\x0c", "\n")
    cleaned = "\n".join(line.rstrip() for line in cleaned.splitlines())
    return cleaned.strip()


__all__ = ["parse_pdf_structure"]
    
