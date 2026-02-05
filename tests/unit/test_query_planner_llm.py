from __future__ import annotations

from typing import cast

import pytest

from retrieval.query_planning.llm import ChatModelLike, generate_query_plan_llm
from schemas.internal.locator import (
    DomainLocatorRule,
    LocatorDefaults,
    LocatorRules,
    QuestionLocatorOverride,
)
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


def _rules() -> LocatorRules:
    return LocatorRules(
        version="test",
        variant="standard",
        defaults=LocatorDefaults(top_k=5),
        domains={
            "D1": DomainLocatorRule(
                section_priors=["methods"],
                keywords=["randomization", "allocation concealment", "sealed opaque envelopes"],
            ),
            "D2": DomainLocatorRule(),
            "D3": DomainLocatorRule(),
            "D4": DomainLocatorRule(),
            "D5": DomainLocatorRule(),
        },
        question_overrides={
            "q1_2": QuestionLocatorOverride(keywords=["central randomization"])
        },
    )


def _question_set() -> QuestionSet:
    return QuestionSet(
        version="test",
        variant="standard",
        questions=[
            Rob2Question(
                question_id="q1_2",
                rob2_id="q1_2",
                domain="D1",
                text="Was the allocation sequence concealed until participants were enrolled and assigned to interventions?",
                options=["Y", "PY", "PN", "N", "NI"],
                order=1,
            )
        ],
    )


def test_generate_query_plan_llm_merges_dedupes_and_limits() -> None:
    llm = _DummyLLM(
        content=(
            '{"query_plan": {"q1_2": ["sealed opaque envelopes", "Sealed Opaque Envelopes", "allocation concealment"]}}'
        )
    )
    plan = generate_query_plan_llm(
        _question_set(),
        _rules(),
        llm=cast(ChatModelLike, llm),
        max_queries_per_question=5,
    )

    queries = plan["q1_2"]
    assert llm.invocations == 1
    assert queries[0].startswith("Was the allocation sequence concealed")
    assert len(queries) <= 5
    assert len(queries) == len({q.casefold() for q in queries})
    assert any("allocation concealment" == q.casefold() for q in queries)


def test_generate_query_plan_llm_missing_question_falls_back_to_deterministic() -> None:
    llm = _DummyLLM(content='{"query_plan": {"unknown": ["randomization"]}}')
    plan = generate_query_plan_llm(
        _question_set(),
        _rules(),
        llm=cast(ChatModelLike, llm),
        max_queries_per_question=5,
    )

    queries = plan["q1_2"]
    assert llm.invocations == 1
    assert len(queries) >= 2
    assert any("randomization" in q.casefold() for q in queries)


def test_generate_query_plan_llm_parses_json_code_block() -> None:
    llm = _DummyLLM(
        content=(
            "```json\n"
            '{"query_plan": {"q1_2": ["sealed opaque envelopes"]}}\n'
            "```"
        )
    )
    plan = generate_query_plan_llm(_question_set(), _rules(), llm=cast(ChatModelLike, llm))
    assert plan["q1_2"][0].startswith("Was the allocation sequence concealed")
    assert any("sealed opaque envelopes" in q for q in plan["q1_2"])


def test_generate_query_plan_llm_parses_json_with_noise() -> None:
    llm = _DummyLLM(
        content=(
            "noise {bad}\\n"
            '{"query_plan": {"q1_2": ["sealed opaque envelopes"]}}'
        )
    )
    plan = generate_query_plan_llm(_question_set(), _rules(), llm=cast(ChatModelLike, llm))
    assert any("sealed opaque envelopes" in q for q in plan["q1_2"])


def test_generate_query_plan_llm_requires_config_if_llm_missing() -> None:
    with pytest.raises(ValueError, match="config is required"):
        generate_query_plan_llm(_question_set(), _rules())


def test_generate_query_plan_llm_max_queries_one_skips_llm() -> None:
    llm = _DummyLLM(content="not used")
    plan = generate_query_plan_llm(
        _question_set(),
        _rules(),
        llm=cast(ChatModelLike, llm),
        max_queries_per_question=1,
    )
    assert llm.invocations == 0
    assert plan["q1_2"] == [_question_set().questions[0].text]
