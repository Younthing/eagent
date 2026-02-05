from __future__ import annotations

import json

from pipelines.graphs.nodes.domain_audit import d1_audit_node
from schemas.internal.decisions import DomainAnswer, DomainDecision
from schemas.internal.documents import DocStructure, SectionSpan
from schemas.internal.rob2 import QuestionSet, Rob2Question


class _DummyResponse:
    def __init__(self, content: str) -> None:
        self.content = content


class _DummyLLM:
    def __init__(self, content: str) -> None:
        self._content = content
        self.invocations = 0

    def with_structured_output(self, _schema: object) -> object:
        raise RuntimeError("structured output not supported in dummy")

    def invoke(self, _messages: object) -> _DummyResponse:
        self.invocations += 1
        return _DummyResponse(self._content)


def test_domain_audit_disabled_is_noop() -> None:
    doc = DocStructure(
        body="Example.",
        sections=[SectionSpan(paragraph_id="p1", title="Methods", page=1, text="Example.")],
    )
    question_set = QuestionSet(
        version="test",
        variant="standard",
        questions=[
            Rob2Question(
                question_id="q1",
                rob2_id="q1",
                domain="D1",
                text="Was randomization described?",
                options=["Y", "PY", "PN", "N", "NI"],
                order=1,
            )
        ],
    )
    out = d1_audit_node(
        {
            "doc_structure": doc.model_dump(),
            "question_set": question_set.model_dump(),
            "validated_candidates": {},
            "domain_audit_mode": "none",
        }
    )
    assert out["domain_audit_report"]["enabled"] is False
    assert out["domain_audit_report"]["domain"] == "D1"
    assert isinstance(out["domain_audit_reports"], list)
    assert out["domain_audit_reports"][0]["domain"] == "D1"


def test_domain_audit_patches_evidence_and_reruns_domain() -> None:
    doc = DocStructure(
        body="Randomization used a random number table.",
        sections=[
            SectionSpan(
                paragraph_id="p1",
                title="Methods",
                page=2,
                text="Randomization used a random number table.",
            )
        ],
    )
    question_set = QuestionSet(
        version="test",
        variant="standard",
        questions=[
            Rob2Question(
                question_id="q1",
                rob2_id="q1",
                domain="D1",
                text="Was randomization described?",
                options=["Y", "PY", "PN", "N", "NI"],
                order=1,
            )
        ],
    )
    initial = DomainDecision(
        domain="D1",
        risk="low",
        risk_rationale="Initial.",
        answers=[
            DomainAnswer(
                question_id="q1",
                answer="NI",
                rationale="Missing.",
                evidence_refs=[],
            )
        ],
        missing_questions=["q1"],
    )

    audit_llm = _DummyLLM(
        json.dumps(
            {
                "answers": [
                    {
                        "question_id": "q1",
                        "answer": "Y",
                        "rationale": "Randomization described.",
                        "evidence": [{"paragraph_id": "p1", "quote": "random number table"}],
                        "confidence": 0.9,
                    }
                ]
            }
        )
    )
    d1_llm = _DummyLLM(
        json.dumps(
            {
                "domain_risk": "low",
                "domain_rationale": "OK.",
                "answers": [
                    {
                        "question_id": "q1",
                        "answer": "Y",
                        "rationale": "Supported.",
                        "evidence": [{"paragraph_id": "p1", "quote": "random number table"}],
                        "confidence": 0.9,
                    }
                ],
            }
        )
    )

    out = d1_audit_node(
        {
            "doc_structure": doc.model_dump(),
            "question_set": question_set.model_dump(),
            "validated_candidates": {},
            "d1_decision": initial.model_dump(),
            "domain_audit_mode": "llm",
            "domain_audit_llm": audit_llm,
            "domain_audit_patch_window": 0,
            "domain_audit_rerun_domains": True,
            "d1_llm": d1_llm,
            "domain_evidence_top_k": 5,
        }
    )

    report = out["domain_audit_report"]
    assert report["enabled"] is True
    assert report["patches_applied"]["q1"] == 1
    assert report["domain_rerun"] is True
    assert out["domain_audit_reports"][0]["domain"] == "D1"

    validated = out["validated_candidates"]["q1"]
    assert validated[0]["paragraph_id"] == "p1"

    updated_decision = DomainDecision.model_validate(out["d1_decision"])
    assert updated_decision.answers[0].answer == "Y"


def test_domain_audit_parses_json_with_noise() -> None:
    doc = DocStructure(
        body="Randomization used a random number table.",
        sections=[
            SectionSpan(
                paragraph_id="p1",
                title="Methods",
                page=2,
                text="Randomization used a random number table.",
            )
        ],
    )
    question_set = QuestionSet(
        version="test",
        variant="standard",
        questions=[
            Rob2Question(
                question_id="q1",
                rob2_id="q1",
                domain="D1",
                text="Was randomization described?",
                options=["Y", "PY", "PN", "N", "NI"],
                order=1,
            )
        ],
    )
    initial = DomainDecision(
        domain="D1",
        risk="low",
        risk_rationale="Initial.",
        answers=[
            DomainAnswer(
                question_id="q1",
                answer="NI",
                rationale="Missing.",
                evidence_refs=[],
            )
        ],
        missing_questions=["q1"],
    )

    audit_payload = {
        "answers": [
            {
                "question_id": "q1",
                "answer": "Y",
                "rationale": "Randomization described.",
                "evidence": [{"paragraph_id": "p1", "quote": "random number table"}],
                "confidence": 0.9,
            }
        ]
    }
    audit_llm = _DummyLLM(f"noise {{bad}}\\n{json.dumps(audit_payload)}")
    d1_llm = _DummyLLM(
        json.dumps(
            {
                "domain_risk": "low",
                "domain_rationale": "OK.",
                "answers": [
                    {
                        "question_id": "q1",
                        "answer": "Y",
                        "rationale": "Supported.",
                        "evidence": [
                            {"paragraph_id": "p1", "quote": "random number table"}
                        ],
                        "confidence": 0.9,
                    }
                ],
            }
        )
    )

    out = d1_audit_node(
        {
            "doc_structure": doc.model_dump(),
            "question_set": question_set.model_dump(),
            "validated_candidates": {},
            "d1_decision": initial.model_dump(),
            "domain_audit_mode": "llm",
            "domain_audit_llm": audit_llm,
            "domain_audit_patch_window": 0,
            "domain_audit_rerun_domains": True,
            "d1_llm": d1_llm,
            "domain_evidence_top_k": 5,
        }
    )

    validated = out["validated_candidates"]["q1"]
    assert validated[0]["paragraph_id"] == "p1"
