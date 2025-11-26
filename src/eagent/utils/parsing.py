"""Docling 驱动的文档解析工具。"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict

from eagent.telemetry import traceable_if_enabled

try:  # pragma: no cover - optional dependency
    from langchain_docling import DoclingLoader
except Exception:  # pragma: no cover
    DoclingLoader = None

MAX_FALLBACK_CHARS = 4000
logger = logging.getLogger(__name__)


@traceable_if_enabled(run_type="parser", name="Docling Parser")
def parse_pdf_structure(source: str | Path) -> Dict[str, str]:
    """使用 Docling 将文件解析为标准结构。

    Args:
        source: 文档路径或原始文本。优先尝试当作文件解析。

    Returns:
        Dict[str, str]: 目前仅包含 `body` 键，值为截断后的全文。

    Raises:
        FileNotFoundError: 当传入路径不存在时会记录警告并退回原始字符串。
    """

    path = Path(str(source))
    text = ""

    if DoclingLoader and path.exists():
        text = _load_with_docling(path)

    if not text:
        text = _read_plain_text(path) if path.exists() else str(source)

    normalized = _normalize_block(text)
    if len(normalized) > MAX_FALLBACK_CHARS:
        normalized = normalized[:MAX_FALLBACK_CHARS]

    return {"body": normalized}


def get_section_context(doc_structure: Dict[str, str], section_filter: str) -> str:
    """返回指定键的内容，如缺失则回退到 `body`。

    Args:
        doc_structure: `parse_pdf_structure` 生成的字典。
        section_filter: 请求的章节名，例如 `methods`。

    Returns:
        str: 匹配到的文本或主体内容。
    """

    if not doc_structure:
        return ""

    if section_filter in doc_structure and doc_structure[section_filter]:
        return doc_structure[section_filter]

    body = doc_structure.get("body")
    if body:
        return body

    fallback = next(iter(doc_structure.values()), "")
    return fallback[:MAX_FALLBACK_CHARS]


def _load_with_docling(path: Path) -> str:
    """通过 DoclingLoader 加载并拼接文本。"""

    try:
        loader = DoclingLoader(file_path=str(path))
        documents = loader.load()
        return "\n\n".join(doc.page_content or "" for doc in documents).strip()
    except Exception as exc:  # pragma: no cover - 记录错误即可
        logger.warning("Docling 解析失败，将尝试纯文本读取: %s", exc)
        return ""


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


__all__ = ["parse_pdf_structure", "get_section_context"]
    
