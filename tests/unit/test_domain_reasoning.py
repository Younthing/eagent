from __future__ import annotations

import json
from typing import cast

from pipelines.graphs.nodes.domains.common import (
    ChatModelLike,
    DomainQuoteValidationConfig,
    run_domain_reasoning,
)
from schemas.internal.evidence import EvidenceSupport, FusedEvidenceCandidate, RelevanceVerdict
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


def _candidate_with_supporting_quote(
    question_id: str,
    paragraph_id: str,
    text: str,
    supporting_quote: str,
) -> dict:
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
        relevance=RelevanceVerdict(
            label="relevant",
            confidence=1.0,
            supporting_quote=supporting_quote,
        ),
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
            ),
            Rob2Question(
                question_id="q1_2",
                rob2_id="q1_2",
                domain="D1",
                text="Was the allocation sequence concealed?",
                options=["Y", "PY", "PN", "N", "NI"],
                order=2,
            ),
            Rob2Question(
                question_id="q1_3",
                rob2_id="q1_3",
                domain="D1",
                text="Did baseline differences suggest a problem?",
                options=["Y", "PY", "PN", "N", "NI"],
                order=3,
            ),
        ],
    )
    validated_candidates = {
        "q1_1": [_candidate("q1_1", "p1", "Allocation used a random number table.")],
        "q1_2": [_candidate("q1_2", "p2", "Allocation sequence was concealed.")],
        "q1_3": [_candidate("q1_3", "p3", "No baseline imbalance reported.")],
    }
    llm = _DummyLLM(
        json.dumps(
            {
                "domain_risk": "high",
                "domain_rationale": "Randomization described.",
                "answers": [
                    {
                        "question_id": "q1_1",
                        "answer": "Y",
                        "rationale": "Random number table reported.",
                        "evidence": [{"paragraph_id": "p1", "quote": "random number table"}],
                        "confidence": 0.8,
                    },
                    {
                        "question_id": "q1_2",
                        "answer": "Y",
                        "rationale": "Concealed allocation.",
                        "evidence": [{"paragraph_id": "p2", "quote": "concealed"}],
                    },
                    {
                        "question_id": "q1_3",
                        "answer": "N",
                        "rationale": "No imbalance.",
                        "evidence": [{"paragraph_id": "p3", "quote": "no imbalance"}],
                    },
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


def test_domain_reasoning_parses_json_with_noise() -> None:
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
        "q1_1": [_candidate("q1_1", "p1", "Allocation used a random number table.")],
    }
    payload = {
        "domain_risk": "high",
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
    llm = _DummyLLM(f"noise {{bad}}\\n{json.dumps(payload)}")
    decision = run_domain_reasoning(
        domain="D1",
        question_set=question_set,
        validated_candidates=validated_candidates,
        llm=cast(ChatModelLike, llm),
        llm_config=None,
    )

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
            Rob2Question(
                question_id="q2a_6",
                rob2_id="q2_6",
                domain="D2",
                effect_type="assignment",
                text="Was an appropriate analysis used to estimate the effect of assignment?",
                options=["Y", "PY", "PN", "N", "NI"],
                order=3,
            ),
            Rob2Question(
                question_id="q2a_7",
                rob2_id="q2_7",
                domain="D2",
                effect_type="assignment",
                text="If N/PN/NI to 2.6: Was there potential impact of failure to analyze?",
                options=["NA", "Y", "PY", "PN", "N", "NI"],
                conditions=[
                    QuestionCondition(
                        operator="any",
                        dependencies=[
                            QuestionDependency(
                                question_id="q2a_6",
                                allowed_answers=["N", "PN", "NI"],
                            )
                        ],
                        note="If N/PN/NI to 2.6",
                    )
                ],
                order=4,
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
        "q2a_6": [
            _candidate("q2a_6", "p3", "Analysis followed ITT."),
        ],
        "q2a_7": [
            _candidate("q2a_7", "p4", "No substantial impact expected."),
        ],
    }
    llm = _DummyLLM(
        json.dumps(
            {
                "domain_risk": "high",
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
                    {
                        "question_id": "q2a_6",
                        "answer": "Y",
                        "rationale": "Appropriate analysis.",
                        "evidence": [{"paragraph_id": "p3", "quote": "ITT"}],
                    },
                    {
                        "question_id": "q2a_7",
                        "answer": "NA",
                        "rationale": "Not applicable.",
                        "evidence": [],
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
    assert decision.risk == "low"
    assert answers["q2a_1"] == "N"
    assert answers["q2a_3"] == "NA"


def test_d2_adherence_rule_override() -> None:
    question_set = QuestionSet(
        version="test",
        variant="standard",
        questions=[
            Rob2Question(
                question_id="q2b_1",
                rob2_id="q2_1",
                domain="D2",
                effect_type="adherence",
                text="Were participants aware of their assigned intervention?",
                options=["Y", "PY", "PN", "N", "NI"],
                order=1,
            ),
            Rob2Question(
                question_id="q2b_2",
                rob2_id="q2_2",
                domain="D2",
                effect_type="adherence",
                text="Were carers aware of participants' assigned intervention?",
                options=["Y", "PY", "PN", "N", "NI"],
                order=2,
            ),
            Rob2Question(
                question_id="q2b_3",
                rob2_id="q2_3",
                domain="D2",
                effect_type="adherence",
                text="If Y/PY/NI to 2.1 or 2.2: Were important non-protocol interventions balanced?",
                options=["NA", "Y", "PY", "PN", "N", "NI"],
                conditions=[
                    QuestionCondition(
                        operator="any",
                        dependencies=[
                            QuestionDependency(
                                question_id="q2b_1",
                                allowed_answers=["Y", "PY", "NI"],
                            ),
                            QuestionDependency(
                                question_id="q2b_2",
                                allowed_answers=["Y", "PY", "NI"],
                            ),
                        ],
                        note="If Y/PY/NI to 2.1 or 2.2",
                    )
                ],
                order=3,
            ),
            Rob2Question(
                question_id="q2b_4",
                rob2_id="q2_4",
                domain="D2",
                effect_type="adherence",
                text="Were there failures in implementing the intervention that could have affected the outcome?",
                options=["NA", "Y", "PY", "PN", "N", "NI"],
                order=4,
            ),
            Rob2Question(
                question_id="q2b_5",
                rob2_id="q2_5",
                domain="D2",
                effect_type="adherence",
                text="Was there non-adherence that could have affected outcomes?",
                options=["NA", "Y", "PY", "PN", "N", "NI"],
                order=5,
            ),
            Rob2Question(
                question_id="q2b_6",
                rob2_id="q2_6",
                domain="D2",
                effect_type="adherence",
                text="If N/PN/NI to 2.3, or Y/PY/NI to 2.4 or 2.5: Was appropriate analysis used?",
                options=["NA", "Y", "PY", "PN", "N", "NI"],
                conditions=[
                    QuestionCondition(
                        operator="any",
                        dependencies=[
                            QuestionDependency(
                                question_id="q2b_3",
                                allowed_answers=["N", "PN", "NI"],
                            ),
                            QuestionDependency(
                                question_id="q2b_4",
                                allowed_answers=["Y", "PY", "NI"],
                            ),
                            QuestionDependency(
                                question_id="q2b_5",
                                allowed_answers=["Y", "PY", "NI"],
                            ),
                        ],
                        note="If N/PN/NI to 2.3, or Y/PY/NI to 2.4 or 2.5",
                    )
                ],
                order=6,
            ),
        ],
    )
    validated_candidates = {
        "q2b_1": [_candidate("q2b_1", "p1", "Participants were blinded.")],
        "q2b_2": [_candidate("q2b_2", "p2", "Personnel were blinded.")],
        "q2b_3": [_candidate("q2b_3", "p3", "No non-protocol interventions.")],
        "q2b_4": [_candidate("q2b_4", "p4", "Implementation was stable.")],
        "q2b_5": [_candidate("q2b_5", "p5", "Adherence was good.")],
        "q2b_6": [_candidate("q2b_6", "p6", "Analysis was appropriate.")],
    }
    llm = _DummyLLM(
        json.dumps(
            {
                "domain_risk": "high",
                "domain_rationale": "Placeholder.",
                "answers": [
                    {
                        "question_id": "q2b_1",
                        "answer": "N",
                        "rationale": "Blinded.",
                        "evidence": [{"paragraph_id": "p1", "quote": "blinded"}],
                    },
                    {
                        "question_id": "q2b_2",
                        "answer": "N",
                        "rationale": "Blinded.",
                        "evidence": [{"paragraph_id": "p2", "quote": "blinded"}],
                    },
                    {
                        "question_id": "q2b_3",
                        "answer": "Y",
                        "rationale": "Balanced.",
                        "evidence": [{"paragraph_id": "p3", "quote": "balanced"}],
                    },
                    {
                        "question_id": "q2b_4",
                        "answer": "N",
                        "rationale": "No failures.",
                        "evidence": [{"paragraph_id": "p4", "quote": "stable"}],
                    },
                    {
                        "question_id": "q2b_5",
                        "answer": "N",
                        "rationale": "Adherence good.",
                        "evidence": [{"paragraph_id": "p5", "quote": "good"}],
                    },
                    {
                        "question_id": "q2b_6",
                        "answer": "Y",
                        "rationale": "Appropriate analysis.",
                        "evidence": [{"paragraph_id": "p6", "quote": "appropriate"}],
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
        effect_type="adherence",
    )

    assert decision.risk == "low"


def test_d3_reasoning_condition_chain_sets_na() -> None:
    question_set = QuestionSet(
        version="test",
        variant="standard",
        questions=[
            Rob2Question(
                question_id="q3_1",
                rob2_id="q3_1",
                domain="D3",
                text="Were data for this outcome available for all, or nearly all, participants randomized?",
                options=["Y", "PY", "PN", "N", "NI"],
                order=1,
            ),
            Rob2Question(
                question_id="q3_2",
                rob2_id="q3_2",
                domain="D3",
                text="If N/PN/NI to 3.1: Is there evidence that the result was not biased by missing outcome data?",
                options=["NA", "Y", "PY", "PN", "N"],
                conditions=[
                    QuestionCondition(
                        operator="any",
                        dependencies=[
                            QuestionDependency(
                                question_id="q3_1",
                                allowed_answers=["N", "PN", "NI"],
                            )
                        ],
                        note="If N/PN/NI to 3.1",
                    )
                ],
                order=2,
            ),
            Rob2Question(
                question_id="q3_3",
                rob2_id="q3_3",
                domain="D3",
                text="If N/PN to 3.2: Could missingness in the outcome depend on its true value?",
                options=["NA", "Y", "PY", "PN", "N", "NI"],
                conditions=[
                    QuestionCondition(
                        operator="any",
                        dependencies=[
                            QuestionDependency(
                                question_id="q3_2",
                                allowed_answers=["N", "PN"],
                            )
                        ],
                        note="If N/PN to 3.2",
                    )
                ],
                order=3,
            ),
            Rob2Question(
                question_id="q3_4",
                rob2_id="q3_4",
                domain="D3",
                text="If Y/PY/NI to 3.3: Is it likely that missingness in the outcome depended on its true value?",
                options=["NA", "Y", "PY", "PN", "N", "NI"],
                conditions=[
                    QuestionCondition(
                        operator="any",
                        dependencies=[
                            QuestionDependency(
                                question_id="q3_3",
                                allowed_answers=["Y", "PY", "NI"],
                            )
                        ],
                        note="If Y/PY/NI to 3.3",
                    )
                ],
                order=4,
            ),
        ],
    )
    validated_candidates = {
        "q3_1": [_candidate("q3_1", "p1", "Follow-up was complete.")],
        "q3_2": [_candidate("q3_2", "p2", "Missing data were minimal.")],
        "q3_3": [_candidate("q3_3", "p3", "Missingness related to outcome.")],
        "q3_4": [_candidate("q3_4", "p4", "Missingness likely related.")],
    }
    llm = _DummyLLM(
        json.dumps(
            {
                "domain_risk": "some concerns",
                "domain_rationale": "Placeholder.",
                "answers": [
                    {
                        "question_id": "q3_1",
                        "answer": "Y",
                        "rationale": "Nearly complete data.",
                        "evidence": [{"paragraph_id": "p1", "quote": "complete"}],
                    },
                    {
                        "question_id": "q3_2",
                        "answer": "Y",
                        "rationale": "Bias unlikely.",
                        "evidence": [{"paragraph_id": "p2", "quote": "minimal"}],
                    },
                    {
                        "question_id": "q3_3",
                        "answer": "Y",
                        "rationale": "Depends on outcome.",
                        "evidence": [{"paragraph_id": "p3", "quote": "related"}],
                    },
                    {
                        "question_id": "q3_4",
                        "answer": "Y",
                        "rationale": "Likely depends.",
                        "evidence": [{"paragraph_id": "p4", "quote": "likely"}],
                    },
                ],
            }
        )
    )
    decision = run_domain_reasoning(
        domain="D3",
        question_set=question_set,
        validated_candidates=validated_candidates,
        llm=cast(ChatModelLike, llm),
        llm_config=None,
    )

    assert decision.risk == "low"
    answers = {answer.question_id: answer.answer for answer in decision.answers}
    assert answers["q3_1"] == "Y"
    assert answers["q3_2"] == "NA"
    assert answers["q3_3"] == "NA"
    assert answers["q3_4"] == "NA"


def test_d4_reasoning_condition_chain_sets_na() -> None:
    question_set = QuestionSet(
        version="test",
        variant="standard",
        questions=[
            Rob2Question(
                question_id="q4_1",
                rob2_id="q4_1",
                domain="D4",
                text="Was the method of measuring the outcome inappropriate?",
                options=["Y", "PY", "PN", "N", "NI"],
                order=1,
            ),
            Rob2Question(
                question_id="q4_2",
                rob2_id="q4_2",
                domain="D4",
                text="Could measurement or ascertainment of the outcome have differed between intervention groups?",
                options=["Y", "PY", "PN", "N", "NI"],
                order=2,
            ),
            Rob2Question(
                question_id="q4_3",
                rob2_id="q4_3",
                domain="D4",
                text="If N/PN/NI to 4.1 and 4.2: Were outcome assessors aware of the intervention received?",
                options=["NA", "Y", "PY", "PN", "N", "NI"],
                conditions=[
                    QuestionCondition(
                        operator="all",
                        dependencies=[
                            QuestionDependency(
                                question_id="q4_1",
                                allowed_answers=["N", "PN", "NI"],
                            ),
                            QuestionDependency(
                                question_id="q4_2",
                                allowed_answers=["N", "PN", "NI"],
                            ),
                        ],
                        note="If N/PN/NI to 4.1 and 4.2",
                    )
                ],
                order=3,
            ),
            Rob2Question(
                question_id="q4_4",
                rob2_id="q4_4",
                domain="D4",
                text="If Y/PY/NI to 4.3: Could assessment have been influenced by knowledge of intervention?",
                options=["NA", "Y", "PY", "PN", "N", "NI"],
                conditions=[
                    QuestionCondition(
                        operator="any",
                        dependencies=[
                            QuestionDependency(
                                question_id="q4_3",
                                allowed_answers=["Y", "PY", "NI"],
                            )
                        ],
                        note="If Y/PY/NI to 4.3",
                    )
                ],
                order=4,
            ),
            Rob2Question(
                question_id="q4_5",
                rob2_id="q4_5",
                domain="D4",
                text="If Y/PY/NI to 4.4: Is it likely that assessment was influenced?",
                options=["NA", "Y", "PY", "PN", "N", "NI"],
                conditions=[
                    QuestionCondition(
                        operator="any",
                        dependencies=[
                            QuestionDependency(
                                question_id="q4_4",
                                allowed_answers=["Y", "PY", "NI"],
                            )
                        ],
                        note="If Y/PY/NI to 4.4",
                    )
                ],
                order=5,
            ),
        ],
    )
    validated_candidates = {
        "q4_1": [_candidate("q4_1", "p1", "Outcome method differed.")],
        "q4_2": [_candidate("q4_2", "p2", "Measurement was consistent.")],
        "q4_3": [_candidate("q4_3", "p3", "Assessors were blinded.")],
        "q4_4": [_candidate("q4_4", "p4", "Assessment may be biased.")],
        "q4_5": [_candidate("q4_5", "p5", "Influence likely.")],
    }
    llm = _DummyLLM(
        json.dumps(
            {
                "domain_risk": "high",
                "domain_rationale": "Placeholder.",
                "answers": [
                    {
                        "question_id": "q4_1",
                        "answer": "Y",
                        "rationale": "Method inappropriate.",
                        "evidence": [{"paragraph_id": "p1", "quote": "method"}],
                    },
                    {
                        "question_id": "q4_2",
                        "answer": "N",
                        "rationale": "No differences.",
                        "evidence": [{"paragraph_id": "p2", "quote": "consistent"}],
                    },
                    {
                        "question_id": "q4_3",
                        "answer": "Y",
                        "rationale": "Assessors knew.",
                        "evidence": [{"paragraph_id": "p3", "quote": "assessors"}],
                    },
                    {
                        "question_id": "q4_4",
                        "answer": "Y",
                        "rationale": "Influenced.",
                        "evidence": [{"paragraph_id": "p4", "quote": "biased"}],
                    },
                    {
                        "question_id": "q4_5",
                        "answer": "Y",
                        "rationale": "Likely influenced.",
                        "evidence": [{"paragraph_id": "p5", "quote": "likely"}],
                    },
                ],
            }
        )
    )
    decision = run_domain_reasoning(
        domain="D4",
        question_set=question_set,
        validated_candidates=validated_candidates,
        llm=cast(ChatModelLike, llm),
        llm_config=None,
    )

    assert decision.risk == "high"
    answers = {answer.question_id: answer.answer for answer in decision.answers}
    assert answers["q4_1"] == "Y"
    assert answers["q4_2"] == "N"
    assert answers["q4_3"] == "NA"
    assert answers["q4_4"] == "NA"
    assert answers["q4_5"] == "NA"


def test_d5_reasoning_parses_answers() -> None:
    question_set = QuestionSet(
        version="test",
        variant="standard",
        questions=[
            Rob2Question(
                question_id="q5_1",
                rob2_id="q5_1",
                domain="D5",
                text="Were the data analyzed per pre-specified plan?",
                options=["Y", "PY", "PN", "N", "NI"],
                order=1,
            ),
            Rob2Question(
                question_id="q5_2",
                rob2_id="q5_2",
                domain="D5",
                text="Was the result selected from multiple eligible outcome measurements?",
                options=["Y", "PY", "PN", "N", "NI"],
                order=2,
            ),
            Rob2Question(
                question_id="q5_3",
                rob2_id="q5_3",
                domain="D5",
                text="Was the result selected from multiple eligible analyses?",
                options=["Y", "PY", "PN", "N", "NI"],
                order=3,
            ),
        ],
    )
    validated_candidates = {
        "q5_1": [_candidate("q5_1", "p1", "Pre-specified analysis plan.")],
        "q5_2": [_candidate("q5_2", "p2", "Multiple scales reported.")],
        "q5_3": [_candidate("q5_3", "p3", "Multiple analyses conducted.")],
    }
    llm = _DummyLLM(
        json.dumps(
            {
                "domain_risk": "some_concerns",
                "domain_rationale": "Selective reporting possible.",
                "answers": [
                    {
                        "question_id": "q5_1",
                        "answer": "Y",
                        "rationale": "Plan specified.",
                        "evidence": [{"paragraph_id": "p1", "quote": "analysis plan"}],
                    },
                    {
                        "question_id": "q5_2",
                        "answer": "PY",
                        "rationale": "Multiple outcomes noted.",
                        "evidence": [{"paragraph_id": "p2", "quote": "scales"}],
                    },
                    {
                        "question_id": "q5_3",
                        "answer": "PN",
                        "rationale": "Analyses were exploratory.",
                        "evidence": [{"paragraph_id": "p3", "quote": "analyses"}],
                    },
                ],
            }
        )
    )
    decision = run_domain_reasoning(
        domain="D5",
        question_set=question_set,
        validated_candidates=validated_candidates,
        llm=cast(ChatModelLike, llm),
        llm_config=None,
    )

    assert decision.risk == "high"
    answers = {answer.question_id: answer.answer for answer in decision.answers}
    assert answers["q5_1"] == "Y"
    assert answers["q5_2"] == "PY"
    assert answers["q5_3"] == "PN"


def _single_question_set() -> QuestionSet:
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


def test_domain_reasoning_quote_invalid_uses_supporting_quote() -> None:
    question_set = _single_question_set()
    validated_candidates = {
        "q1_1": [
            _candidate_with_supporting_quote(
                "q1_1",
                "p1",
                "Allocation used a random number table.",
                "random number table",
            )
        ]
    }
    llm = _DummyLLM(
        json.dumps(
            {
                "domain_risk": "high",
                "domain_rationale": "Randomization described.",
                "answers": [
                    {
                        "question_id": "q1_1",
                        "answer": "Y",
                        "rationale": "Random number table reported.",
                        "evidence": [{"paragraph_id": "p1", "quote": "wrong quote"}],
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

    assert decision.answers[0].evidence_refs[0].quote == "random number table"


def test_domain_reasoning_quote_invalid_drops_quote() -> None:
    question_set = _single_question_set()
    validated_candidates = {
        "q1_1": [_candidate("q1_1", "p1", "Allocation used a random number table.")],
    }
    llm = _DummyLLM(
        json.dumps(
            {
                "domain_risk": "high",
                "domain_rationale": "Randomization described.",
                "answers": [
                    {
                        "question_id": "q1_1",
                        "answer": "Y",
                        "rationale": "Random number table reported.",
                        "evidence": [{"paragraph_id": "p1", "quote": "wrong quote"}],
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

    assert decision.answers[0].evidence_refs[0].quote is None


def test_domain_reasoning_quote_validation_disabled_keeps_llm_quote() -> None:
    question_set = _single_question_set()
    validated_candidates = {
        "q1_1": [_candidate("q1_1", "p1", "Allocation used a random number table.")],
    }
    llm = _DummyLLM(
        json.dumps(
            {
                "domain_risk": "high",
                "domain_rationale": "Randomization described.",
                "answers": [
                    {
                        "question_id": "q1_1",
                        "answer": "Y",
                        "rationale": "Random number table reported.",
                        "evidence": [{"paragraph_id": "p1", "quote": "wrong quote"}],
                        "confidence": 0.8,
                    }
                ],
            }
        )
    )
    quote_config = DomainQuoteValidationConfig(
        enabled=False,
        match_policy="folded_casefold",
        fallback="supporting_quote",
    )

    decision = run_domain_reasoning(
        domain="D1",
        question_set=question_set,
        validated_candidates=validated_candidates,
        llm=cast(ChatModelLike, llm),
        llm_config=None,
        quote_config=quote_config,
    )

    assert decision.answers[0].evidence_refs[0].quote == "wrong quote"


def test_domain_reasoning_quote_match_policy_folded_casefold() -> None:
    question_set = _single_question_set()
    validated_candidates = {
        "q1_1": [_candidate("q1_1", "p1", "Allocation used a Random Number Table.")],
    }
    llm = _DummyLLM(
        json.dumps(
            {
                "domain_risk": "high",
                "domain_rationale": "Randomization described.",
                "answers": [
                    {
                        "question_id": "q1_1",
                        "answer": "Y",
                        "rationale": "Random number table reported.",
                        "evidence": [
                            {"paragraph_id": "p1", "quote": "random   number table"}
                        ],
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

    assert decision.answers[0].evidence_refs[0].quote == "random   number table"
