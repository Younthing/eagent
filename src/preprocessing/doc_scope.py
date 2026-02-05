"""Doc scope selector for mixed-document PDFs."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Iterable, List, Sequence

from schemas.internal.documents import DocStructure, FigureSpan, SectionSpan
from utils.text import normalize_block

_DOI_RE = re.compile(r"10\.\d{4,9}/[^\s\"'<>]+", re.IGNORECASE)
_EN_WORD_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)

_ABSTRACT_PATTERNS = (r"\babstract\b", "摘要")
_KEYWORDS_PATTERNS = (r"\bkey\s*words?\b", r"\bkeywords?\b", "关键词")
_INTRO_PATTERNS = (r"\bintroduction\b", r"\bbackground\b", "引言", "背景")
_METHODS_PATTERNS = (
    r"\bmethods?\b",
    r"\bmaterials?\s+and\s+methods?\b",
    "方法",
    "材料与方法",
)
_RESULTS_PATTERNS = (r"\bresults?\b", "结果")
_DISCUSSION_PATTERNS = (r"\bdiscussion\b", "讨论")
_REFERENCES_PATTERNS = (r"\breferences?\b", r"\bbibliography\b", "参考文献", "参考資料", "参考文獻")


@dataclass(frozen=True)
class _StartCandidate:
    index: int
    page: int | None
    dois: set[str]


def parse_page_range(text: str) -> set[int]:
    """Parse page ranges like '1-3,5,7-9'."""
    if not text:
        return set()
    cleaned = text.strip()
    if not cleaned:
        return set()
    pages: set[int] = set()
    for part in re.split(r"[;,]", cleaned):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start_str, end_str = part.split("-", 1)
            start = int(start_str.strip())
            end = int(end_str.strip())
            if start <= 0 or end <= 0:
                raise ValueError("page range must be positive")
            if start > end:
                start, end = end, start
            pages.update(range(start, end + 1))
        else:
            value = int(part)
            if value <= 0:
                raise ValueError("page range must be positive")
            pages.add(value)
    return pages


def parse_paragraph_ids(value: list[str] | str) -> set[str]:
    """Parse paragraph ids from list or comma-separated string."""
    items: list[str] = []
    if isinstance(value, list):
        items = [str(item) for item in value]
    else:
        raw = value.strip()
        if not raw:
            return set()
        if raw.startswith("["):
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, list):
                items = [str(item) for item in parsed]
            else:
                items = [raw]
        else:
            items = re.split(r"[,\n;]", raw)

    result: set[str] = set()
    for item in items:
        cleaned = str(item).strip()
        if cleaned:
            result.add(cleaned)
    return result


def apply_doc_scope(
    doc: DocStructure,
    *,
    mode: str,
    include_paragraph_ids: set[str] | None,
    page_range: str | None,
    min_pages: int,
    min_confidence: float,
    abstract_gap_pages: int,
) -> tuple[DocStructure, dict]:
    """Apply doc scope selection to a DocStructure."""
    mode_normalized = (mode or "auto").strip().lower()
    report: dict = {
        "enabled": mode_normalized != "none",
        "mode": mode_normalized,
        "selected_pages": [],
        "excluded_pages": [],
        "selected_paragraph_ids": [],
        "start_candidate_pages": [],
        "confidence": 0.0,
        "reason": "skipped",
    }

    if mode_normalized == "none":
        report["reason"] = "disabled"
        return doc, report

    if mode_normalized == "manual":
        return _apply_manual_scope(doc, include_paragraph_ids, page_range, report)

    if mode_normalized != "auto":
        raise ValueError("doc_scope_mode must be 'auto', 'manual', or 'none'")

    return _apply_auto_scope(
        doc,
        report,
        min_pages=min_pages,
        min_confidence=min_confidence,
        abstract_gap_pages=abstract_gap_pages,
    )


def _apply_manual_scope(
    doc: DocStructure,
    include_paragraph_ids: set[str] | None,
    page_range: str | None,
    report: dict,
) -> tuple[DocStructure, dict]:
    paragraph_ids = include_paragraph_ids or set()
    pages: set[int] = set()

    if not paragraph_ids and page_range:
        pages = parse_page_range(page_range)

    if not paragraph_ids and not pages:
        raise ValueError("manual doc scope requires paragraph ids or page range")

    if paragraph_ids:
        kept = [span for span in doc.sections if span.paragraph_id in paragraph_ids]
        report["selected_paragraph_ids"] = sorted(paragraph_ids)
        report["reason"] = "manual_paragraph_ids"
    else:
        kept: list[SectionSpan] = []
        for span in doc.sections:
            span_pages = _span_pages(span)
            if span_pages and span_pages & pages:
                kept.append(span)
        report["selected_pages"] = sorted(pages)
        report["reason"] = "manual_page_range"

    if not kept:
        raise ValueError("manual doc scope produced empty document")

    rebuilt = _rebuild_doc_structure(doc, kept)
    _fill_report_pages(report, doc, kept)
    report["confidence"] = 1.0
    return rebuilt, report


def _apply_auto_scope(
    doc: DocStructure,
    report: dict,
    *,
    min_pages: int,
    min_confidence: float,
    abstract_gap_pages: int,
) -> tuple[DocStructure, dict]:
    spans = list(doc.sections)
    if not spans:
        report["reason"] = "empty_document"
        return doc, report

    pages_by_span: list[set[int] | None] = [_span_pages(span) for span in spans]
    known_pages = sorted({page for pages in pages_by_span if pages for page in pages})
    total_pages = len(known_pages)
    unknown_count = sum(1 for pages in pages_by_span if not pages)

    report["total_pages"] = total_pages
    report["unknown_span_ratio"] = (
        round(unknown_count / max(len(spans), 1), 3)
        if spans
        else 1.0
    )

    if total_pages == 0 or report["unknown_span_ratio"] > 0.5:
        report["reason"] = "missing_page_info"
        return doc, report

    if total_pages < max(min_pages, 1):
        report["reason"] = "short_doc"
        return doc, report

    start_candidates = _find_start_candidates(spans, pages_by_span)
    filtered_candidates = _filter_duplicate_candidates(start_candidates, abstract_gap_pages)
    report["start_candidate_pages"] = [
        candidate.page for candidate in filtered_candidates if candidate.page is not None
    ]

    if len(filtered_candidates) < 2:
        report["reason"] = "insufficient_signals"
        return doc, report

    similarity_breaks = _compute_similarity_breaks(spans, pages_by_span, known_pages)
    report["similarity_break_at"] = similarity_breaks

    doi_sets = [candidate.dois for candidate in filtered_candidates if candidate.dois]
    distinct_dois = sorted({doi for group in doi_sets for doi in group})
    report["doi_values"] = distinct_dois[:10]

    confidence = 0.6
    if len(distinct_dois) >= 2:
        confidence += 0.25
    if similarity_breaks:
        confidence += 0.15
    confidence = min(confidence, 0.95)
    report["confidence"] = round(confidence, 2)

    if confidence < min_confidence:
        report["reason"] = "confidence_too_low"
        return doc, report

    segments = _build_segments(filtered_candidates, len(spans))
    selected = _select_best_segment(spans, segments)
    if selected is None:
        report["reason"] = "no_segment"
        return doc, report

    start_idx, end_idx = selected
    start_idx = _extend_start_to_page(spans, pages_by_span, start_idx)
    kept = spans[start_idx : end_idx + 1]
    if not kept:
        report["reason"] = "empty_selection"
        return doc, report

    rebuilt = _rebuild_doc_structure(doc, kept)
    _fill_report_pages(report, doc, kept)
    report["selected_paragraph_ids"] = [span.paragraph_id for span in kept]
    report["reason"] = "scoped"
    return rebuilt, report


def _span_pages(span: SectionSpan) -> set[int] | None:
    if span.pages:
        pages = {page for page in span.pages if isinstance(page, int)}
        return pages or None
    if isinstance(span.page, int):
        return {span.page}
    return None


def _find_start_candidates(
    spans: Sequence[SectionSpan],
    pages_by_span: Sequence[set[int] | None],
) -> list[_StartCandidate]:
    candidates: list[_StartCandidate] = []
    for idx, span in enumerate(spans):
        text = _span_text(span)
        has_abstract = _contains_any(text, _ABSTRACT_PATTERNS)
        if not has_abstract:
            continue
        has_keywords = _contains_any(text, _KEYWORDS_PATTERNS)
        dois = _extract_dois(text)
        if has_keywords or dois:
            page = None
            pages = pages_by_span[idx]
            if pages:
                page = min(pages)
            candidates.append(_StartCandidate(index=idx, page=page, dois=dois))
    return candidates


def _filter_duplicate_candidates(
    candidates: Sequence[_StartCandidate],
    abstract_gap_pages: int,
) -> list[_StartCandidate]:
    if not candidates:
        return []
    filtered: list[_StartCandidate] = []
    for candidate in candidates:
        if not filtered:
            filtered.append(candidate)
            continue
        prev = filtered[-1]
        if (
            candidate.page is not None
            and prev.page is not None
            and candidate.page - prev.page < max(1, abstract_gap_pages)
        ):
            if candidate.dois and prev.dois and candidate.dois.isdisjoint(prev.dois):
                filtered.append(candidate)
            else:
                continue
        else:
            filtered.append(candidate)
    return filtered


def _build_segments(
    candidates: Sequence[_StartCandidate],
    total_spans: int,
) -> list[tuple[int, int]]:
    segments: list[tuple[int, int]] = []
    for idx, candidate in enumerate(candidates):
        start = candidate.index
        end = total_spans - 1
        if idx + 1 < len(candidates):
            end = max(candidates[idx + 1].index - 1, start)
        segments.append((start, end))
    return segments


def _select_best_segment(
    spans: Sequence[SectionSpan],
    segments: Sequence[tuple[int, int]],
) -> tuple[int, int] | None:
    best: tuple[int, int] | None = None
    best_score: float = -1.0
    for start, end in segments:
        subset = spans[start : end + 1]
        if not subset:
            continue
        char_count = sum(len(span.text or "") for span in subset)
        signals = _segment_signals(subset)
        bonus = 0
        if signals.get("methods"):
            bonus += 3
        if signals.get("results"):
            bonus += 2
        if signals.get("discussion"):
            bonus += 2
        if signals.get("references"):
            bonus += 1
        score = char_count + bonus * 1000
        if best is None:
            best_score = score
            best = (start, end)
            continue

        if score > best_score:
            # Prefer earlier segments when the improvement is marginal.
            if start > best[0]:
                epsilon = max(200.0, best_score * 0.05)
                if score - best_score < epsilon:
                    continue
            best_score = score
            best = (start, end)
        elif score == best_score and start < best[0]:
            best = (start, end)
    return best


def _segment_signals(spans: Sequence[SectionSpan]) -> dict[str, bool]:
    flags = {"methods": False, "results": False, "discussion": False, "references": False}
    for span in spans:
        text = _span_text(span)
        if not flags["methods"] and _contains_any(text, _METHODS_PATTERNS):
            flags["methods"] = True
        if not flags["results"] and _contains_any(text, _RESULTS_PATTERNS):
            flags["results"] = True
        if not flags["discussion"] and _contains_any(text, _DISCUSSION_PATTERNS):
            flags["discussion"] = True
        if not flags["references"] and _contains_any(text, _REFERENCES_PATTERNS):
            flags["references"] = True
    return flags


def _extend_start_to_page(
    spans: Sequence[SectionSpan],
    pages_by_span: Sequence[set[int] | None],
    start_idx: int,
) -> int:
    pages = pages_by_span[start_idx]
    if not pages:
        return start_idx
    target_page = min(pages)
    idx = start_idx
    while idx > 0:
        prev_pages = pages_by_span[idx - 1]
        if prev_pages and target_page in prev_pages:
            idx -= 1
            continue
        break
    return idx


def _compute_similarity_breaks(
    spans: Sequence[SectionSpan],
    pages_by_span: Sequence[set[int] | None],
    known_pages: Sequence[int],
) -> list[int]:
    if len(known_pages) < 2:
        return []

    page_texts: dict[int, str] = {page: "" for page in known_pages}
    for idx, span in enumerate(spans):
        pages = pages_by_span[idx]
        if not pages:
            continue
        for page in pages:
            page_texts[page] += " " + _span_text(span)

    token_sets: dict[int, set[str]] = {}
    df: dict[str, int] = {}
    for page in known_pages:
        tokens = _tokenize_mixed(page_texts.get(page, ""))
        token_set = set(tokens)
        token_sets[page] = token_set
        for token in token_set:
            df[token] = df.get(token, 0) + 1

    threshold = max(1, int(len(known_pages) * 0.6))
    common_tokens = {token for token, count in df.items() if count > threshold}

    for page in known_pages:
        token_sets[page] = {token for token in token_sets[page] if token not in common_tokens}

    breaks: list[int] = []
    for prev_page, next_page in zip(known_pages, known_pages[1:]):
        prev_tokens = token_sets.get(prev_page) or set()
        next_tokens = token_sets.get(next_page) or set()
        if not prev_tokens or not next_tokens:
            continue
        overlap = prev_tokens & next_tokens
        union = prev_tokens | next_tokens
        similarity = len(overlap) / max(len(union), 1)
        if similarity < 0.05:
            breaks.append(next_page)
    return breaks


def _tokenize_mixed(text: str) -> list[str]:
    lowered = text.lower()
    tokens = _EN_WORD_RE.findall(lowered)
    tokens.extend(_cjk_bigrams(text))
    return tokens


def _cjk_bigrams(text: str) -> list[str]:
    chars = [char for char in text if _is_cjk(char)]
    if len(chars) < 2:
        return []
    return ["".join(chars[i : i + 2]) for i in range(len(chars) - 1)]


def _is_cjk(char: str) -> bool:
    code = ord(char)
    return (
        0x3400 <= code <= 0x4DBF
        or 0x4E00 <= code <= 0x9FFF
        or 0xF900 <= code <= 0xFAFF
    )


def _span_text(span: SectionSpan) -> str:
    title = span.title or ""
    text = span.text or ""
    return f"{title}\n{text}".strip()


def _contains_any(text: str, patterns: Sequence[str]) -> bool:
    for pattern in patterns:
        if "\\" in pattern or pattern.startswith("(?"):
            if re.search(pattern, text, re.IGNORECASE):
                return True
        else:
            if pattern.lower() in text.lower():
                return True
    return False


def _extract_dois(text: str) -> set[str]:
    dois: set[str] = set()
    for match in _DOI_RE.findall(text):
        cleaned = match.rstrip(").,;:")
        if cleaned:
            dois.add(cleaned.lower())
    return dois


def _rebuild_doc_structure(
    doc: DocStructure, kept: Sequence[SectionSpan]
) -> DocStructure:
    body = normalize_block("\n\n".join(span.text for span in kept))
    section_map = _aggregate_sections_by_title(kept)
    selected_pages: set[int] = set()
    for span in kept:
        pages = _span_pages(span)
        if pages:
            selected_pages.update(pages)
    figures = _filter_figures(doc.figures, selected_pages)
    payload = {
        "body": body,
        "sections": list(kept),
        "figures": figures,
        "spans": list(kept),
        **section_map,
    }
    if doc.docling_config is not None:
        payload["docling_config"] = doc.docling_config
    return DocStructure.model_validate(payload)


def _aggregate_sections_by_title(spans: Iterable[SectionSpan]) -> dict[str, str]:
    aggregated: dict[str, List[str]] = {}
    for span in spans:
        title = span.title.strip() if isinstance(span.title, str) else ""
        text = span.text.strip() if isinstance(span.text, str) else ""
        if not title or title.lower() == "body" or not text:
            continue
        aggregated.setdefault(title, []).append(text)
    return {title: "\n\n".join(parts) for title, parts in aggregated.items()}


def _filter_figures(
    figures: Sequence[FigureSpan],
    selected_pages: set[int],
) -> list[FigureSpan]:
    if not figures:
        return []
    if not selected_pages:
        return list(figures)
    kept: list[FigureSpan] = []
    for figure in figures:
        pages = set(figure.pages or [])
        if figure.page is not None:
            pages.add(figure.page)
        if not pages or pages & selected_pages:
            kept.append(figure)
    return kept


def _fill_report_pages(report: dict, doc: DocStructure, kept: Sequence[SectionSpan]) -> None:
    all_pages: set[int] = set()
    for span in doc.sections:
        pages = _span_pages(span)
        if pages:
            all_pages.update(pages)
    selected_pages: set[int] = set()
    for span in kept:
        pages = _span_pages(span)
        if pages:
            selected_pages.update(pages)
    report["selected_pages"] = sorted(selected_pages)
    report["excluded_pages"] = sorted(all_pages - selected_pages)
