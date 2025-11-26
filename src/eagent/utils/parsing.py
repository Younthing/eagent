"""Utility helpers for turning plain text into structured sections."""

from __future__ import annotations

import os
from difflib import get_close_matches
import re
from pathlib import Path
from typing import Dict, Mapping, Optional

SectionMap = Mapping[str, str]

SECTION_ALIASES: Dict[str, set[str]] = {
    "abstract": {"abstract", "summary", "overview"},
    "introduction": {"introduction", "background"},
    "related_work": {"related_work", "literature_review"},
    "methods": {"methods", "method", "methodology"},
    "experiments": {"experiments", "experiment_setup"},
    "dataset": {"dataset", "data"},
    "results": {"results", "findings"},
    "evaluation": {"evaluation", "analysis"},
    "discussion": {"discussion"},
    "conclusion": {"conclusion", "conclusions"},
    "future_work": {"future_work", "limitations"},
    "appendix": {"appendix", "supplementary"},
}

ALIAS_TO_CANONICAL = {
    alias: canonical
    for canonical, aliases in SECTION_ALIASES.items()
    for alias in {canonical, *aliases}
}

HEADER_PATTERN = re.compile(
    r"^(?P<prefix>(?:#{1,6}\s+|[0-9]+\.\s+)*)?(?P<title>[A-Za-z][A-Za-z0-9\s/-]{2,})\s*:?\s*$"
)


def parse_pdf_structure(source: str | os.PathLike[str]) -> Dict[str, str]:
    """Best-effort parser returning a section map consumed by the graph."""

    raw_text = _load_text(source)
    sections = _extract_sections(raw_text)
    normalized_body = _normalize_block(raw_text)
    sections["body"] = normalized_body
    return sections


def get_section_context(doc_structure: SectionMap, section_filter: str) -> str:
    """Return content for the requested section, falling back to best matches."""

    if not doc_structure:
        return ""

    if section_filter in doc_structure:
        return doc_structure[section_filter]

    normalized = _normalize_section_name(section_filter)
    if normalized in doc_structure:
        return doc_structure[normalized]

    alias_target = ALIAS_TO_CANONICAL.get(normalized)
    if alias_target and alias_target in doc_structure:
        return doc_structure[alias_target]

    for key, value in doc_structure.items():
        if _normalize_section_name(key) == normalized:
            return value

    matches = get_close_matches(
        section_filter, list(doc_structure.keys()), n=1, cutoff=0.55
    )
    if matches:
        return doc_structure[matches[0]]

    return doc_structure.get("body", next(iter(doc_structure.values()), ""))


def _load_text(source: str | os.PathLike[str]) -> str:
    """Return file contents if the path exists, otherwise treat as inline text."""

    candidate = Path(str(source))
    if candidate.exists() and candidate.is_file():
        return candidate.read_text(encoding="utf-8")
    return str(source)


def _extract_sections(text: str) -> Dict[str, str]:
    """Simple parser that splits the text by markdown-style headings."""

    lines = text.replace("\r\n", "\n").splitlines()
    sections: Dict[str, str] = {}
    buffer: list[str] = []
    current_key: Optional[str] = None

    def flush() -> None:
        nonlocal buffer, current_key
        if not buffer:
            return
        content = _normalize_block("\n".join(buffer))
        buffer = []
        if not content:
            return

        key = current_key or "preamble"
        existing = sections.get(key)
        sections[key] = f"{existing}\n\n{content}" if existing else content

    for line in lines:
        header = _match_section_header(line)
        if header:
            flush()
            current_key = header
            continue
        buffer.append(line)

    flush()
    return sections


def _match_section_header(line: str) -> Optional[str]:
    stripped = line.strip()
    if not stripped:
        return None

    match = HEADER_PATTERN.match(stripped)
    if not match:
        return None

    normalized = _normalize_section_name(match.group("title"))
    canonical = ALIAS_TO_CANONICAL.get(normalized)
    if canonical:
        return canonical

    if stripped.startswith("#") or stripped.endswith(":") or stripped.isupper():
        return normalized

    return None


def _normalize_block(text: str) -> str:
    cleaned = text.replace("\r\n", "\n").replace("\x0c", "\n")
    cleaned = "\n".join(line.rstrip() for line in cleaned.splitlines())
    return cleaned.strip()


def _normalize_section_name(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.lower().strip())
    slug = re.sub(r"_+", "_", slug)
    return slug.strip("_")


__all__ = ["parse_pdf_structure", "get_section_context"]
    