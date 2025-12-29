from __future__ import annotations

import json
from typing import Any, cast

from schemas.internal.documents import DocStructure, SectionSpan
from schemas.internal.rob2 import QuestionSet, Rob2Question

from pipelines.graphs.rob2_graph import build_rob2_graph


class _DummyResponse:
    def __init__(self, content: str) -> None:
        self.content = content


class _DummyRelevanceLLM:
    def __init__(self) -> None:
        self.invocations = 0

    def with_structured_output(self, _schema: object) -> object:
        raise RuntimeError("structured output not supported in dummy")

    def invoke(self, _messages: object) -> _DummyResponse:
        self.invocations += 1
        text = ""
        try:
            messages = cast(list[object], _messages)
            if messages:
                user = messages[-1]
                content = getattr(user, "content", "")
                if isinstance(content, str):
                    payload = json.loads(content)
                    text = str(((payload or {}).get("paragraph") or {}).get("text") or "")
        except Exception:
            text = ""

        quote = None
        if "random number table" in text:
            quote = "random number table"
        elif "sealed envelopes" in text:
            quote = "sealed envelopes"

        return _DummyResponse(
            json.dumps(
                {
                    "label": "relevant",
                    "confidence": 0.9,
                    "supporting_quote": quote,
                }
            )
        )


class _DummyConsistencyLLM:
    def __init__(self) -> None:
        self.invocations = 0

    def with_structured_output(self, _schema: object) -> object:
        raise RuntimeError("structured output not supported in dummy")

    def invoke(self, _messages: object) -> _DummyResponse:
        self.invocations += 1
        if self.invocations == 1:
            return _DummyResponse(
                """{
                  "label":"fail",
                  "confidence":0.9,
                  "conflicts":[
                    {
                      "paragraph_id_a":"p1",
                      "paragraph_id_b":"p2",
                      "reason":"conflict in allocation description",
                      "quote_a":"random number table",
                      "quote_b":"sealed envelopes"
                    }
                  ]
                }"""
            )
        return _DummyResponse('{"label":"pass","confidence":0.9,"conflicts":[]}')


def _doc() -> DocStructure:
    return DocStructure(
        body="Allocation used a random number table. Allocation was concealed using sealed envelopes.",
        sections=[
            SectionSpan(
                paragraph_id="p1",
                title="Methods",
                page=2,
                text="Allocation used a random number table.",
            ),
            SectionSpan(
                paragraph_id="p2",
                title="Methods",
                page=2,
                text="Allocation was concealed using sealed envelopes.",
            ),
        ],
    )


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


def test_rob2_workflow_retries_on_consistency_fail_and_recovers() -> None:
    calls: dict[str, int] = {"rule_based": 0}

    def preprocess_stub(state: dict) -> dict:
        return {"doc_structure": cast(dict, state["doc_structure"])}

    def planner_stub(state: dict) -> dict:
        return {"question_set": cast(dict, state["question_set"])}

    def rule_based_locator_stub(state: dict) -> dict:
        calls["rule_based"] += 1
        return {
            "rule_based_candidates": {
                "q1_1": [
                    {
                        "question_id": "q1_1",
                        "paragraph_id": "p1",
                        "title": "Methods",
                        "page": 2,
                        "text": "Allocation used a random number table.",
                        "source": "rule_based",
                        "score": 10.0,
                    },
                    {
                        "question_id": "q1_1",
                        "paragraph_id": "p2",
                        "title": "Methods",
                        "page": 2,
                        "text": "Allocation was concealed using sealed envelopes.",
                        "source": "rule_based",
                        "score": 9.0,
                    },
                ]
            },
            "rule_based_evidence": [],
            "rule_based_rules_version": "test",
        }

    def empty_locator_stub(_state: dict) -> dict:
        return {"bm25_candidates": {}, "bm25_evidence": [], "bm25_debug": {}}

    def empty_splade_stub(_state: dict) -> dict:
        return {"splade_candidates": {}, "splade_evidence": [], "splade_debug": {}}

    app = build_rob2_graph(
        node_overrides={
            "preprocess": preprocess_stub,
            "planner": planner_stub,
            "rule_based_locator": rule_based_locator_stub,
            "bm25_locator": empty_locator_stub,
            "splade_locator": empty_splade_stub,
        }
    )

    relevance_llm = _DummyRelevanceLLM()
    consistency_llm = _DummyConsistencyLLM()

    final: dict[str, Any] = cast(
        dict[str, Any],
        app.invoke(
            {
                "doc_structure": _doc().model_dump(),
                "question_set": _question_set().model_dump(),
                "top_k": 2,
                "fusion_top_k": 2,
                "relevance_validator": "llm",
                "relevance_llm": relevance_llm,
                "relevance_min_confidence": 0.6,
                "relevance_require_quote": True,
                "existence_require_text_match": True,
                "existence_require_quote_in_source": True,
                "consistency_validator": "llm",
                "consistency_llm": consistency_llm,
                "consistency_min_confidence": 0.6,
                "completeness_enforce": True,
                "validation_max_retries": 1,
                "validation_fail_on_consistency": True,
            }
        ),
    )

    assert calls["rule_based"] == 2  # initial + retry
    assert relevance_llm.invocations >= 4  # 2 candidates x 2 attempts
    assert consistency_llm.invocations == 2  # fail then pass

    assert final["validation_attempt"] == 1
    retry_log = final.get("validation_retry_log") or []
    assert isinstance(retry_log, list)
    assert len(retry_log) == 1
    assert (retry_log[0] or {}).get("consistency_failed_questions") == ["q1_1"]

    assert final["completeness_passed"] is True
    assert final.get("consistency_failed_questions") == []
