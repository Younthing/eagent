from __future__ import annotations

import json
from typing import cast

from pipelines.graphs.nodes.domains.common import ChatModelLike, run_domain_reasoning
from schemas.internal.evidence import EvidenceSupport, FusedEvidenceCandidate
from schemas.internal.rob2 import QuestionCondition, QuestionDependency, QuestionSet, Rob2Question


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


def _candidate(question_id: str, paragraph_id: str, text: str) -> dict:
    return FusedEvidenceCandidate(
        question_id=question_id,
        paragraph_id=paragraph_id,
        title="Methods",
        page=2,
        text=text,
        fusion_score=0.8,
        fusion_rank=1,
        support_count=1,
        supports=[EvidenceSupport(engine="rule_based", rank=1, score=1.0)],
    ).model_dump()


def test_d1_reasoning_parses_answers_and_evidence() -> None:
    question_set = QuestionSet(
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
    validated_candidates = {
        "q1_1": [
            _candidate("q1_1", "p1", "Allocation used a random number table."),
        ]
    }
    llm = _DummyLLM(
        json.dumps(
            {
                "domain_risk": "low",
                "domain_rationale": "Randomization described.",
                "answers": [
                    {
                        "question_id": "q1_1",
                        "answer": "Y",
                        "rationale": "Random number table reported.",
                        "evidence": [{"paragraph_id": "p1", "quote": "random number table"}],
                        "confidence": 0.8,
                    }
                ],
            }
        )
    )
    decision = run_domain_reasoning(
        domain="D1",
        question_set=question_set,
        validated_candidates=validated_candidates,
        llm=cast(ChatModelLike, llm),
        llm_config=None,
    )

    assert decision.domain == "D1"
    assert decision.risk == "low"
    assert decision.answers[0].answer == "Y"
    assert decision.answers[0].evidence_refs[0].paragraph_id == "p1"


def test_d2_reasoning_enforces_conditions() -> None:
    question_set = QuestionSet(
        version="test",
        variant="standard",
        questions=[
            Rob2Question(
                question_id="q2a_1",
                rob2_id="q2_1",
                domain="D2",
                effect_type="assignment",
                text="Were participants aware of their assigned intervention during the trial?",
                options=["Y", "PY", "PN", "N", "NI"],
                order=1,
            ),
            Rob2Question(
                question_id="q2a_3",
                rob2_id="q2_3",
                domain="D2",
                effect_type="assignment",
                text="If Y/PY/NI to 2.1 or 2.2: Were there deviations from the intended intervention?",
                options=["NA", "Y", "PY", "PN", "N", "NI"],
                conditions=[
                    QuestionCondition(
                        operator="any",
                        dependencies=[
                            QuestionDependency(
                                question_id="q2a_1",
                                allowed_answers=["Y", "PY", "NI"],
                            )
                        ],
                        note="If Y/PY/NI to 2.1",
                    )
                ],
                order=2,
            ),
        ],
    )
    validated_candidates = {
        "q2a_1": [
            _candidate("q2a_1", "p1", "Participants were blinded."),
        ],
        "q2a_3": [
            _candidate("q2a_3", "p2", "No deviations were reported."),
        ],
    }
    llm = _DummyLLM(
        json.dumps(
            {
                "domain_risk": "some concerns",
                "domain_rationale": "Placeholder.",
                "answers": [
                    {
                        "question_id": "q2a_1",
                        "answer": "N",
                        "rationale": "Blinded participants.",
                        "evidence": [{"paragraph_id": "p1", "quote": "blinded"}],
                    },
                    {
                        "question_id": "q2a_3",
                        "answer": "Y",
                        "rationale": "Deviations occurred.",
                        "evidence": [{"paragraph_id": "p2", "quote": "deviations"}],
                    },
                ],
            }
        )
    )
    decision = run_domain_reasoning(
        domain="D2",
        question_set=question_set,
        validated_candidates=validated_candidates,
        llm=cast(ChatModelLike, llm),
        llm_config=None,
        effect_type="assignment",
    )

    answers = {answer.question_id: answer.answer for answer in decision.answers}
    assert answers["q2a_1"] == "N"
    assert answers["q2a_3"] == "NA"
