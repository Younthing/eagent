from typing import Dict

from eagent.telemetry import traceable_if_enabled

MAX_FALLBACK_CHARS = 2000


@traceable_if_enabled(run_type="parser", name="PDF Structure Parser")
def parse_pdf_structure(file_path: str) -> Dict[str, str]:
    """
    模拟解析 PDF 并切分章节。
    在真实场景中，这里会调用 PyPDF2 或 Unstructured。
    """
    return {
        "abstract": "This paper proposes a new Transformer architecture...",
        "methods": "We utilized a 12-layer attention mechanism with...",
        "results": "Our model achieved 98.5% accuracy on the test set...",
        "conclusion": "Future work includes...",
    }


def get_section_context(doc: Dict[str, str], section_key: str) -> str:
    """Return requested section with truncated fallback to avoid large prompts."""

    section = doc.get(section_key)
    if section:
        return section

    fallback = str(doc)
    return fallback[:MAX_FALLBACK_CHARS]
