from __future__ import annotations

from evidence.validators.existence import annotate_existence
from schemas.internal.documents import DocStructure, SectionSpan
from schemas.internal.evidence import (
    EvidenceSupport,
    ExistenceVerdict,
    FusedEvidenceCandidate,
    RelevanceVerdict,
)


def _doc() -> DocStructure:
    return DocStructure(
        body="Allocation used a random number table.",
        sections=[
            SectionSpan(
                paragraph_id="p1",
                title="Methods",
                page=2,
                text="Allocation used a random number table.",
            )
        ],
    )


def _candidate(*, paragraph_id: str, text: str, quote: str | None) -> FusedEvidenceCandidate:
    return FusedEvidenceCandidate(
        question_id="q1_1",
        paragraph_id=paragraph_id,
        title="Methods",
        page=2,
        text=text,
        fusion_score=0.03,
        fusion_rank=1,
        support_count=1,
        supports=[EvidenceSupport(engine="bm25", rank=1, score=1.0, query="random number table")],
        relevance=RelevanceVerdict(
            label="relevant",
            confidence=0.9,
            supporting_quote=quote,
        )
        if quote is not None
        else None,
    )


def test_annotate_existence_passes_when_paragraph_and_quote_exist() -> None:
    annotated = annotate_existence(
        _doc(),
        [_candidate(paragraph_id="p1", text="Allocation used a random number table.", quote="random number table")],
    )
    assert annotated[0].existence is not None
    assert annotated[0].existence == ExistenceVerdict(
        label="pass",
        reason=None,
        paragraph_id_found=True,
        text_match=True,
        quote_found=True,
    )


def test_annotate_existence_fails_when_paragraph_missing() -> None:
    annotated = annotate_existence(
        _doc(),
        [_candidate(paragraph_id="missing", text="Allocation used a random number table.", quote=None)],
    )
    assert annotated[0].existence is not None
    assert annotated[0].existence.label == "fail"
    assert annotated[0].existence.reason == "paragraph_id_not_found"


def test_annotate_existence_fails_when_quote_not_found() -> None:
    annotated = annotate_existence(
        _doc(),
        [_candidate(paragraph_id="p1", text="Allocation used a random number table.", quote="sealed envelopes")],
    )
    assert annotated[0].existence is not None
    assert annotated[0].existence.label == "fail"
    assert annotated[0].existence.reason == "quote_not_found"
