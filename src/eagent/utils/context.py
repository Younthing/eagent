"""Document context lookup helpers separated from parsing logic."""

from __future__ import annotations

from typing import Dict

from eagent.utils.parsing import MAX_FALLBACK_CHARS


def get_section_context(doc_structure: Dict[str, object], section_filter: str) -> str:
    """Return the most relevant chunk for a requested section name."""

    if not doc_structure:
        return ""

    normalized = (section_filter or "").strip().lower()

    if normalized:
        direct_match = _match_exact(doc_structure, normalized)
        if direct_match:
            return direct_match

        fuzzy_match = _match_fuzzy(doc_structure, normalized)
        if fuzzy_match:
            return fuzzy_match

    return _default_context(doc_structure)


def _match_exact(doc_structure: Dict[str, object], normalized: str) -> str:
    for key, value in doc_structure.items():
        if key.lower() == normalized and isinstance(value, str) and value:
            return value
    return ""


def _match_fuzzy(doc_structure: Dict[str, object], normalized: str) -> str:
    for key, value in doc_structure.items():
        if normalized in key.lower() and isinstance(value, str) and value:
            return value
    return ""


def _default_context(doc_structure: Dict[str, object]) -> str:
    body = doc_structure.get("body")
    if isinstance(body, str) and body:
        return body

    sections = doc_structure.get("sections")
    if isinstance(sections, list):
        for section in sections:
            if isinstance(section, dict):
                text = section.get("text")
                if isinstance(text, str) and text:
                    return text[:MAX_FALLBACK_CHARS]

    fallback = next((v for v in doc_structure.values() if isinstance(v, str)), "")
    return fallback[:MAX_FALLBACK_CHARS]


__all__ = ["get_section_context"]
