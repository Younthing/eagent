"""Deterministic existence validator for evidence candidates (Milestone 7).

This validator ensures that candidate paragraph references are grounded in the
parsed document structure:
- paragraph_id exists
- candidate text matches the source span (or is a substring)
- supporting_quote (when provided) is present in the source paragraph text
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence

from schemas.internal.documents import DocStructure, SectionSpan
from schemas.internal.evidence import ExistenceVerdict, FusedEvidenceCandidate
from utils.text import normalize_block


@dataclass(frozen=True)
class ExistenceValidatorConfig:
    require_text_match: bool = True
    require_quote_in_source: bool = True


def annotate_existence(
    doc_structure: DocStructure,
    candidates: Sequence[FusedEvidenceCandidate],
    *,
    config: ExistenceValidatorConfig | None = None,
) -> List[FusedEvidenceCandidate]:
    """Annotate candidates with an existence verdict."""
    cfg = config or ExistenceValidatorConfig()
    spans_by_pid = {span.paragraph_id: span for span in doc_structure.sections}

    annotated: List[FusedEvidenceCandidate] = []
    for candidate in candidates:
        span = spans_by_pid.get(candidate.paragraph_id)
        verdict = _judge_candidate(span, candidate, cfg)
        annotated.append(candidate.model_copy(update={"existence": verdict}))

    return annotated


def _judge_candidate(
    span: SectionSpan | None,
    candidate: FusedEvidenceCandidate,
    cfg: ExistenceValidatorConfig,
) -> ExistenceVerdict:
    if span is None:
        return ExistenceVerdict(
            label="fail",
            reason="paragraph_id_not_found",
            paragraph_id_found=False,
            text_match=None,
            quote_found=None,
        )

    source_text = span.text or ""
    candidate_text = candidate.text or ""
    source_norm = normalize_block(source_text)
    candidate_norm = normalize_block(candidate_text)

    text_match = False
    if source_norm and candidate_norm:
        text_match = (
            candidate_norm == source_norm
            or candidate_norm in source_norm
            or source_norm in candidate_norm
        )

    if cfg.require_text_match and not text_match:
        return ExistenceVerdict(
            label="fail",
            reason="text_mismatch",
            paragraph_id_found=True,
            text_match=text_match,
            quote_found=None,
        )

    quote_found: bool | None = None
    quote = None
    if candidate.relevance is not None:
        quote = candidate.relevance.supporting_quote
    if quote:
        quote_found = quote in source_text
        if cfg.require_quote_in_source and not quote_found:
            return ExistenceVerdict(
                label="fail",
                reason="quote_not_found",
                paragraph_id_found=True,
                text_match=text_match,
                quote_found=quote_found,
            )

    return ExistenceVerdict(
        label="pass",
        reason=None,
        paragraph_id_found=True,
        text_match=text_match if source_norm and candidate_norm else None,
        quote_found=quote_found,
    )


__all__ = ["ExistenceValidatorConfig", "annotate_existence"]
