"""LLM-based document metadata extraction."""

from __future__ import annotations

import os
import re
from typing import Any, Iterable, List, Sequence, cast

import langextract as lx

from schemas.internal.documents import DocStructure, SectionSpan
from schemas.internal.metadata import (
    DocumentMetadata,
    DocumentMetadataExtraction,
    DocumentMetadataSource,
)
from utils.text import normalize_block

_YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")
_WHITESPACE = re.compile(r"\s+")


def extract_document_metadata(
    doc_structure: DocStructure,
    *,
    mode: str,
    model_id: str,
    max_chars: int,
    extraction_passes: int,
    max_output_tokens: int,
    base_url: str | None = None,
) -> DocumentMetadata | None:
    if str(mode or "").strip().lower() == "none":
        return None

    text = (doc_structure.body or "").strip()
    if not text:
        text = "\n\n".join(span.text for span in doc_structure.sections if span.text)
    snippet = text[: max(0, int(max_chars or 0))] if max_chars else text

    extraction_meta = DocumentMetadataExtraction(
        method="langextract",
        model_id=model_id,
        provider="anthropic",
    )

    resolved_base_url = base_url or os.getenv("ANTHROPIC_BASE_URL")

    try:
        _ensure_anthropic_schema()
        _ensure_anthropic_base_url()
        result = lx.extract(
            text_or_documents=snippet,
            prompt_description=_build_prompt(),
            examples=_build_examples(),
            model_id=model_id,
            model_url=resolved_base_url,
            use_schema_constraints=True,
            extraction_passes=max(1, int(extraction_passes)),
            language_model_params={"max_tokens": int(max_output_tokens)},
            max_char_buffer=max(1, int(max_chars)),
        )
        annotated = _normalize_result(result)
        metadata = _build_metadata_from_extractions(
            annotated.extractions or [], doc_structure.sections
        )
        metadata.extraction = extraction_meta
        return metadata
    except Exception as exc:
        extraction_meta.error = str(exc)[:500]
        return DocumentMetadata(extraction=extraction_meta)


def _normalize_result(result: object) -> lx.data.AnnotatedDocument:
    if isinstance(result, list):
        return result[0]
    if isinstance(result, lx.data.AnnotatedDocument):
        return result
    raise ValueError("Unexpected LangExtract result type.")


def _build_prompt() -> str:
    return (
        "Extract publication metadata in order of appearance.\n"
        "Use exact text spans for each extraction. Do not paraphrase.\n"
        "Do not overlap entities. If an item is missing, skip it.\n"
        "Use these classes: title, author, affiliation, date, funding.\n"
        "Add attributes when helpful (e.g., date type: received/accepted/published)."
    )


def _build_examples() -> list[lx.data.ExampleData]:
    example_text = (
        "EFFICACY OF XYZ IN TREATMENT\n"
        "Jane Doe, John Smith\n"
        "Department of Psychiatry, University of Example, London, UK\n"
        "Funding: Supported by ABC Foundation grant 1234\n"
        "(Received 12 March 2021; accepted 20 June 2021)"
    )
    return [
        lx.data.ExampleData(
            text=example_text,
            extractions=[
                lx.data.Extraction(
                    extraction_class="title",
                    extraction_text="EFFICACY OF XYZ IN TREATMENT",
                    attributes={"type": "article_title"},
                ),
                lx.data.Extraction(
                    extraction_class="author",
                    extraction_text="Jane Doe",
                    attributes={"role": "author"},
                ),
                lx.data.Extraction(
                    extraction_class="author",
                    extraction_text="John Smith",
                    attributes={"role": "author"},
                ),
                lx.data.Extraction(
                    extraction_class="affiliation",
                    extraction_text="Department of Psychiatry, University of Example, London, UK",
                    attributes={"kind": "institution"},
                ),
                lx.data.Extraction(
                    extraction_class="funding",
                    extraction_text="Supported by ABC Foundation grant 1234",
                    attributes={"funder": "ABC Foundation"},
                ),
                lx.data.Extraction(
                    extraction_class="date",
                    extraction_text="Received 12 March 2021",
                    attributes={"type": "received"},
                ),
                lx.data.Extraction(
                    extraction_class="date",
                    extraction_text="accepted 20 June 2021",
                    attributes={"type": "accepted"},
                ),
            ],
        )
    ]


def _build_metadata_from_extractions(
    extractions: Sequence[lx.data.Extraction],
    spans: Sequence[SectionSpan],
) -> DocumentMetadata:
    title: str | None = None
    authors_raw: List[str] = []
    affiliations_raw: List[str] = []
    funders_raw: List[str] = []
    date_texts: List[str] = []

    for extraction in extractions:
        cls = str(extraction.extraction_class or "").strip().lower()
        text = str(extraction.extraction_text or "").strip()
        if not text:
            continue
        if cls == "title" and title is None:
            title = text
        elif cls == "author":
            authors_raw.append(text)
        elif cls == "affiliation":
            affiliations_raw.append(text)
        elif cls == "funding":
            funders_raw.append(text)
        elif cls == "date":
            date_texts.append(text)

    authors = _dedupe_texts(authors_raw)
    affiliations = _dedupe_texts(affiliations_raw)
    funders = _dedupe_texts(funders_raw)
    year, year_source = _extract_year(date_texts)

    used_texts: List[str] = []
    if title:
        used_texts.append(title)
    used_texts.extend(authors)
    used_texts.extend(affiliations)
    used_texts.extend(funders)
    if year_source:
        used_texts.append(year_source)

    sources = _build_sources(used_texts, spans)

    return DocumentMetadata(
        title=title,
        authors=authors,
        year=year,
        affiliations=affiliations,
        funders=funders,
        sources=sources,
    )


def _dedupe_texts(values: Iterable[str]) -> List[str]:
    seen: set[str] = set()
    output: List[str] = []
    for value in values:
        normalized = _fold_whitespace(value)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        output.append(value)
    return output


def _extract_year(date_texts: Sequence[str]) -> tuple[int | None, str | None]:
    for text in date_texts:
        match = _YEAR_RE.search(text)
        if match:
            return int(match.group(0)), text
    return None, None


def _build_sources(
    used_texts: Sequence[str],
    spans: Sequence[SectionSpan],
) -> List[DocumentMetadataSource]:
    sources: List[DocumentMetadataSource] = []
    seen: set[tuple[str, str]] = set()
    for text in used_texts:
        pid = _find_paragraph_id_by_quote(text, spans)
        if not pid:
            continue
        key = (pid, text)
        if key in seen:
            continue
        seen.add(key)
        sources.append(DocumentMetadataSource(paragraph_id=pid, quote=text))
    return sources


def _find_paragraph_id_by_quote(
    quote: str, spans: Sequence[SectionSpan]
) -> str | None:
    if not quote:
        return None
    for span in spans:
        if quote in (span.text or ""):
            return span.paragraph_id

    folded = _fold_whitespace(quote)
    if folded:
        for span in spans:
            if folded in _fold_whitespace(span.text or ""):
                return span.paragraph_id

    lowered = folded.lower() if folded else ""
    if lowered:
        for span in spans:
            if lowered in _fold_whitespace(span.text or "").lower():
                return span.paragraph_id
    return None


def _fold_whitespace(text: str) -> str:
    return _WHITESPACE.sub(" ", normalize_block(text or "")).strip()


def _ensure_anthropic_schema() -> None:
    try:
        from langextract_anthropic.schema import AnthropicSchema
    except Exception:
        return

    abstract_methods = getattr(AnthropicSchema, "__abstractmethods__", frozenset())
    if "requires_raw_output" not in abstract_methods:
        return

    def _requires_raw_output(self) -> bool:
        return True

    AnthropicSchema.requires_raw_output = property(_requires_raw_output)
    AnthropicSchema.__abstractmethods__ = frozenset(
        name for name in abstract_methods if name != "requires_raw_output"
    )


def _ensure_anthropic_base_url() -> None:
    try:
        from langextract_anthropic import provider as anth_provider
    except Exception:
        return

    if getattr(anth_provider.AnthropicLanguageModel, "_patched_base_url", False):
        return

    original_init = anth_provider.AnthropicLanguageModel.__init__

    def _patched_init(self, *args, **kwargs) -> None:
        base_url = kwargs.pop("base_url", None) or kwargs.pop("model_url", None)
        original_init(self, *args, **kwargs)
        if base_url:
            from anthropic import Anthropic

            self._client = Anthropic(api_key=self.api_key, base_url=base_url)
            self._base_url = base_url

    setattr(cast(Any, anth_provider.AnthropicLanguageModel), "__init__", _patched_init)
    anth_provider.AnthropicLanguageModel._patched_base_url = True


__all__ = ["extract_document_metadata"]
