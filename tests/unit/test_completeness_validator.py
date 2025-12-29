from __future__ import annotations

from typing import Literal

from pipelines.graphs.nodes.validators.completeness import completeness_validator_node
from schemas.internal.evidence import (
    EvidenceSupport,
    ExistenceVerdict,
    FusedEvidenceCandidate,
    RelevanceVerdict,
)
from schemas.internal.rob2 import QuestionSet, Rob2Question


def _question_set() -> QuestionSet:
    return QuestionSet(
        version="test",
        variant="standard",
        questions=[
            Rob2Question(
                question_id="q1_1",
                rob2_id="q1_1",
                domain="D1",
                text="Was the allocation sequence random?",
                options=["Y", "PY", "PN", "N", "NI"],
                order=1,
            )
        ],
    )


def _candidate(
    *,
    relevance_label: Literal["relevant", "irrelevant", "unknown", "none"],
    existence_label: Literal["pass", "fail", "none"],
) -> FusedEvidenceCandidate:
    relevance = (
        RelevanceVerdict(label=relevance_label, confidence=0.9, supporting_quote=None)
        if relevance_label != "none"
        else None
    )
    existence = (
        ExistenceVerdict(
            label=existence_label,
            reason=None if existence_label == "pass" else "text_mismatch",
            paragraph_id_found=True,
            text_match=True if existence_label == "pass" else False,
            quote_found=None,
        )
        if existence_label != "none"
        else None
    )
    return FusedEvidenceCandidate(
        question_id="q1_1",
        paragraph_id="p1",
        title="Methods",
        page=2,
        text="Allocation used a random number table.",
        fusion_score=0.03,
        fusion_rank=1,
        support_count=1,
        supports=[EvidenceSupport(engine="bm25", rank=1, score=1.0, query="random number table")],
        relevance=relevance,
        existence=existence,
    )


def test_completeness_node_emits_validated_evidence_when_passed() -> None:
    state = {
        "question_set": _question_set().model_dump(),
        "relevance_mode": "llm",
        "existence_candidates": {
            "q1_1": [
                _candidate(relevance_label="relevant", existence_label="pass").model_dump(),
                _candidate(relevance_label="irrelevant", existence_label="pass").model_dump(),
            ]
        },
        "validated_top_k": 1,
        "relevance_min_confidence": 0.6,
        "completeness_enforce": True,
    }
    out = completeness_validator_node(state)

    assert out["completeness_passed"] is True
    assert out["validated_candidates"]["q1_1"]
    assert len(out["validated_evidence"]) == 1
    assert out["validated_evidence"][0]["question_id"] == "q1_1"
    assert len(out["validated_evidence"][0]["items"]) == 1


def test_completeness_node_fails_when_enforced_and_missing() -> None:
    state = {
        "question_set": _question_set().model_dump(),
        "relevance_mode": "llm",
        "existence_candidates": {
            "q1_1": [
                _candidate(relevance_label="irrelevant", existence_label="pass").model_dump(),
            ]
        },
        "validated_top_k": 1,
        "relevance_min_confidence": 0.6,
        "completeness_enforce": True,
    }
    out = completeness_validator_node(state)

    assert out["completeness_passed"] is False
    assert out["completeness_failed_questions"] == ["q1_1"]


def test_completeness_node_allows_pass_when_relevance_not_required() -> None:
    state = {
        "question_set": _question_set().model_dump(),
        "relevance_mode": "none",
        "existence_candidates": {
            "q1_1": [
                _candidate(relevance_label="unknown", existence_label="pass").model_dump(),
            ]
        },
        "validated_top_k": 1,
        "relevance_min_confidence": 0.6,
        "completeness_enforce": True,
    }
    out = completeness_validator_node(state)

    assert out["completeness_passed"] is True
    assert out["validated_candidates"]["q1_1"]
