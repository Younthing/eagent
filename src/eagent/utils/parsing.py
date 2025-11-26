"""轻量级文档解析工具。"""

from pathlib import Path
from typing import Dict

from eagent.telemetry import traceable_if_enabled

MAX_FALLBACK_CHARS = 2000


@traceable_if_enabled(run_type="parser", name="Document Loader")
def parse_pdf_structure(source: str) -> Dict[str, str]:
    """读取文件内容或原始字符串，并包装成标准文档结构。

    Args:
        source: 待解析的绝对/相对路径，或直接传入的原始字符串。

    Returns:
        Dict[str, str]: 仅包含 `body` 键的字典，值为去除首尾空白后的文本。

    Notes:
        - 该函数不再负责章节划分，只保证读取内容成功。
        - 未找到文件时，会把输入字符串当作内容，并在必要时截断。
    """

    path = Path(source)
    if path.exists():
        content = path.read_text(encoding="utf-8", errors="ignore")
    else:
        content = source

    normalized = (content or "").strip()
    if not normalized:
        return {"body": ""}

    if len(normalized) > MAX_FALLBACK_CHARS:
        normalized = normalized[:MAX_FALLBACK_CHARS]

    return {"body": normalized}


def get_section_context(doc: Dict[str, str], section_key: str) -> str:
    """获取指定键或回退到 `body` 内容。

    Args:
        doc: `parse_pdf_structure` 返回的文档字典。
        section_key: 需要查找的键名（如 `methods`、`body` 等）。

    Returns:
        str: 找到对应键时返回原文，未命中时回退到 `body` 或整体字符串。
    """

    section = doc.get(section_key)
    if section:
        return section

    body = doc.get("body")
    if body:
        return body

    fallback = str(doc)
    return fallback[:MAX_FALLBACK_CHARS]
