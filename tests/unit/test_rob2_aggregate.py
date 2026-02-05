from __future__ import annotations

from pipelines.graphs.nodes.aggregate import aggregate_node
from schemas.internal.decisions import DomainAnswer, DomainDecision, EvidenceRef
from schemas.internal.documents import DocStructure, SectionSpan
from schemas.internal.metadata import DocumentMetadata, DocumentMetadataExtraction, DocumentMetadataSource
from schemas.internal.rob2 import QuestionSet, Rob2Question


def _doc() -> DocStructure:
    return DocStructure(
        body="P1. P2.",
        sections=[
            SectionSpan(paragraph_id="p1", title="Methods", page=1, text="P1."),
            SectionSpan(paragraph_id="p2", title="Results", page=2, text="P2."),
        ],
    )


def _question_set() -> QuestionSet:
    return QuestionSet(
        version="test",
        variant="standard",
        questions=[
            Rob2Question(
                question_id="q1",
                rob2_id="1.1",
                domain="D1",
                text="D1 question",
                options=["Y", "PY", "PN", "N", "NI"],
                order=1,
            )
        ],
    )


def _empty(domain: str, *, risk: str) -> DomainDecision:
    return DomainDecision(
        domain=domain,  # type: ignore[arg-type]
        risk=risk,  # type: ignore[arg-type]
        risk_rationale="stub",
        answers=[],
        missing_questions=[],
        rule_trace=[],
    )


def test_aggregate_overall_risk_high_when_any_domain_high() -> None:
    out = aggregate_node(
        {
            "doc_structure": _doc().model_dump(),
            "question_set": _question_set().model_dump(),
            "d1_decision": _empty("D1", risk="low").model_dump(),
            "d2_decision": _empty("D2", risk="some_concerns").model_dump(),
            "d3_decision": _empty("D3", risk="high").model_dump(),
            "d4_decision": _empty("D4", risk="low").model_dump(),
            "d5_decision": _empty("D5", risk="low").model_dump(),
        }
    )
    rob2 = out["rob2_result"]
    assert rob2["overall"]["risk"] == "high"


def test_aggregate_overall_risk_high_when_multiple_concerns() -> None:
    out = aggregate_node(
        {
            "doc_structure": _doc().model_dump(),
            "question_set": _question_set().model_dump(),
            "d1_decision": _empty("D1", risk="low").model_dump(),
            "d2_decision": _empty("D2", risk="some_concerns").model_dump(),
            "d3_decision": _empty("D3", risk="some_concerns").model_dump(),
            "d4_decision": _empty("D4", risk="low").model_dump(),
            "d5_decision": _empty("D5", risk="low").model_dump(),
        }
    )
    rob2 = out["rob2_result"]
    assert rob2["overall"]["risk"] == "some_concerns"


def test_aggregate_builds_citation_index() -> None:
    d1 = DomainDecision(
        domain="D1",
        risk="low",
        risk_rationale="ok",
        answers=[
            DomainAnswer(
                question_id="q1",
                answer="Y",
                rationale="supported",
                evidence_refs=[
                    EvidenceRef(paragraph_id="p1", page=1, title="Methods", quote="P1")
                ],
            )
        ],
        missing_questions=[],
        rule_trace=["D1:R3 q1_2 in YES & q1_3 in NO/NI & q1_1 in YES/NI -> low"],
    )
    out = aggregate_node(
        {
            "doc_structure": _doc().model_dump(),
            "question_set": _question_set().model_dump(),
            "d1_decision": d1.model_dump(),
            "d2_decision": _empty("D2", risk="low").model_dump(),
            "d3_decision": _empty("D3", risk="low").model_dump(),
            "d4_decision": _empty("D4", risk="low").model_dump(),
            "d5_decision": _empty("D5", risk="low").model_dump(),
        }
    )
    citations = out["rob2_result"]["citations"]
    assert len(citations) == 1
    assert citations[0]["paragraph_id"] == "p1"
    assert citations[0]["uses"][0]["domain"] == "D1"
    assert citations[0]["uses"][0]["question_id"] == "q1"


def test_aggregate_includes_rule_trace() -> None:
    d1 = DomainDecision(
        domain="D1",
        risk="low",
        risk_rationale="ok",
        answers=[],
        missing_questions=[],
        rule_trace=["D1:R3 q1_2 in YES & q1_3 in NO/NI & q1_1 in YES/NI -> low"],
    )
    out = aggregate_node(
        {
            "doc_structure": _doc().model_dump(),
            "question_set": _question_set().model_dump(),
            "d1_decision": d1.model_dump(),
            "d2_decision": _empty("D2", risk="low").model_dump(),
            "d3_decision": _empty("D3", risk="low").model_dump(),
            "d4_decision": _empty("D4", risk="low").model_dump(),
            "d5_decision": _empty("D5", risk="low").model_dump(),
        }
    )
    domains = out["rob2_result"]["domains"]
    d1_out = next(domain for domain in domains if domain["domain"] == "D1")
    assert d1_out["rule_trace"] == d1.rule_trace


def test_aggregate_includes_document_metadata() -> None:
    metadata = DocumentMetadata(
        title="Example Title",
        authors=["Author A"],
        year=1997,
        affiliations=["Example Institute"],
        funders=["Example Foundation"],
        sources=[DocumentMetadataSource(paragraph_id="p1", quote="Author A")],
        extraction=DocumentMetadataExtraction(
            method="langextract",
            model_id="anthropic-claude-3-5-sonnet-latest",
            provider="anthropic",
        ),
    )
    doc = _doc().model_copy(update={"document_metadata": metadata})
    out = aggregate_node(
        {
            "doc_structure": doc.model_dump(),
            "question_set": _question_set().model_dump(),
            "d1_decision": _empty("D1", risk="low").model_dump(),
            "d2_decision": _empty("D2", risk="low").model_dump(),
            "d3_decision": _empty("D3", risk="low").model_dump(),
            "d4_decision": _empty("D4", risk="low").model_dump(),
            "d5_decision": _empty("D5", risk="low").model_dump(),
        }
    )
    rob2 = out["rob2_result"]
    assert rob2["document_metadata"]["title"] == "Example Title"
    assert rob2["document_metadata"]["authors"] == ["Author A"]
