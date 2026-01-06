"""Shared helpers for CLI subcommands."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

import typer

from core.config import get_settings
from pipelines.graphs.nodes.preprocess import parse_docling_pdf, filter_reference_sections
from retrieval.engines.splade import DEFAULT_SPLADE_MODEL_ID
from rob2.question_bank import DEFAULT_QUESTION_BANK, load_question_bank
from schemas.internal.documents import DocStructure
from schemas.internal.evidence import EvidenceCandidate, FusedEvidenceCandidate
from schemas.internal.rob2 import QuestionSet


DEFAULT_LOCAL_SPLADE = Path(__file__).resolve().parents[3] / "models" / "splade_distil_CoCodenser_large"


def load_doc_structure(
    pdf_path: Path,
    *,
    drop_references: bool | None = None,
    reference_titles: list[str] | str | None = None,
) -> DocStructure:
    if not pdf_path.exists():
        raise typer.BadParameter(f"PDF not found: {pdf_path}")
    settings = get_settings()
    doc_structure = parse_docling_pdf(pdf_path)
    if drop_references is None:
        drop_references = settings.preprocess_drop_references
    if drop_references:
        if reference_titles is None:
            reference_titles = settings.preprocess_reference_titles
        doc_structure = filter_reference_sections(
            doc_structure, reference_titles=reference_titles
        )
    return doc_structure


def load_question_set(path: Path | None = None) -> QuestionSet:
    resolved = path or DEFAULT_QUESTION_BANK
    return load_question_bank(resolved)


def resolve_splade_model(model_id: str | None) -> str:
    if model_id:
        return model_id
    if DEFAULT_LOCAL_SPLADE.exists():
        return str(DEFAULT_LOCAL_SPLADE)
    settings = get_settings()
    if settings.splade_model_id:
        return settings.splade_model_id
    return DEFAULT_SPLADE_MODEL_ID


def preview(text: str, limit: int = 220) -> str:
    collapsed = " ".join(text.split())
    if len(collapsed) <= limit:
        return collapsed
    return collapsed[: limit - 3] + "..."


def emit_json(data: Any) -> None:
    typer.echo(json.dumps(data, ensure_ascii=False, indent=2))


def print_candidates(
    question_id: str,
    candidates: Iterable[EvidenceCandidate | FusedEvidenceCandidate],
    *,
    limit: int,
    full: bool,
) -> None:
    items = list(candidates)
    selected = items if full else items[:limit]
    typer.echo(f"Candidates: {len(items)} (printing {len(selected)})")
    for idx, candidate in enumerate(selected, start=1):
        score = getattr(candidate, "score", None)
        score_label = f"{score:.3f}" if isinstance(score, (int, float)) else "-"
        page = candidate.page if candidate.page is not None else "-"
        title = candidate.title or "-"
        typer.echo(
            f"{idx:>2}. score={score_label} pid={candidate.paragraph_id} page={page} title={title}"
        )
        typer.echo(f"    text: {preview(candidate.text)}")
