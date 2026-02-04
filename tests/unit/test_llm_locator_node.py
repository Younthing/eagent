from __future__ import annotations

from pipelines.graphs.nodes.locators.llm_locator import llm_locator_node
from schemas.internal.evidence import EvidenceCandidate
from schemas.internal.rob2 import QuestionSet, Rob2Question


class _DummyResponse:
    def __init__(self, content: str) -> None:
        self.content = content


class _DummyLLM:
    def __init__(self, content: str | list[str]) -> None:
        if isinstance(content, list):
            self._contents = content
        else:
            self._contents = [content]
        self.invocations = 0
        self._index = 0

    def with_structured_output(self, _schema: object) -> object:
        raise RuntimeError("structured output not supported in dummy")

    def invoke(self, _messages: object) -> _DummyResponse:
        self.invocations += 1
        content = self._contents[min(self._index, len(self._contents) - 1)]
        if self._index < len(self._contents) - 1:
            self._index += 1
        return _DummyResponse(content)


def test_llm_locator_node_emits_supporting_quote() -> None:
    question_set = QuestionSet(
        version="test",
        variant="standard",
        questions=[
            Rob2Question(
                question_id="q1",
                rob2_id="q1",
                domain="D1",
                text="Was the allocation sequence random?",
                options=["Y", "N"],
                order=1,
            )
        ],
    )

    llm = _DummyLLM(
        content='{"sufficient":true,"evidence":[{"paragraph_id":"p1","quote":"random number table"}],"expand":{"keywords":[],"section_priors":[],"queries":[]}}'
    )
    state = {
        "question_set": question_set.model_dump(),
        "doc_structure": {
            "body": "",
            "sections": [
                {
                    "paragraph_id": "p1",
                    "title": "Methods",
                    "page": 1,
                    "text": "Allocation used a random number table.",
                }
            ],
        },
        "rule_based_candidates": {
            "q1": [
                EvidenceCandidate(
                    question_id="q1",
                    paragraph_id="p1",
                    title="Methods",
                    page=1,
                    text="Allocation used a random number table.",
                    source="rule_based",
                    score=1.0,
                ).model_dump()
            ]
        },
        "llm_locator_mode": "llm",
        "llm_locator_llm": llm,
        "llm_locator_max_steps": 1,
        "llm_locator_seed_top_n": 1,
        "llm_locator_per_step_top_n": 1,
        "llm_locator_max_candidates": 5,
    }

    out = llm_locator_node(state)

    candidates = out["fulltext_candidates"]["q1"]
    assert len(candidates) == 1
    assert candidates[0]["supporting_quote"] == "random number table"
    assert candidates[0]["engine"] == "llm_locator"


def test_llm_locator_node_drops_invalid_quote() -> None:
    question_set = QuestionSet(
        version="test",
        variant="standard",
        questions=[
            Rob2Question(
                question_id="q1",
                rob2_id="q1",
                domain="D1",
                text="Was the allocation sequence random?",
                options=["Y", "N"],
                order=1,
            )
        ],
    )

    llm = _DummyLLM(
        content='{"sufficient":true,"evidence":[{"paragraph_id":"p1","quote":"not in text"}],"expand":{"keywords":[],"section_priors":[],"queries":[]}}'
    )
    state = {
        "question_set": question_set.model_dump(),
        "doc_structure": {
            "body": "",
            "sections": [
                {
                    "paragraph_id": "p1",
                    "title": "Methods",
                    "page": 1,
                    "text": "Allocation used a random number table.",
                }
            ],
        },
        "llm_locator_mode": "llm",
        "llm_locator_llm": llm,
        "llm_locator_max_steps": 1,
        "llm_locator_seed_top_n": 1,
        "llm_locator_per_step_top_n": 1,
        "llm_locator_max_candidates": 5,
    }

    out = llm_locator_node(state)
    candidates = out["fulltext_candidates"]["q1"]
    assert candidates == []


def test_llm_locator_node_expands_and_recovers() -> None:
    question_set = QuestionSet(
        version="test",
        variant="standard",
        questions=[
            Rob2Question(
                question_id="q1",
                rob2_id="q1",
                domain="D1",
                text="Was the allocation sequence random?",
                options=["Y", "N"],
                order=1,
            )
        ],
    )

    llm = _DummyLLM(
        [
            '{"sufficient":false,"evidence":[],"expand":{"keywords":["allocation"],"section_priors":["methods"],"queries":[]}}',
            '{"sufficient":true,"evidence":[{"paragraph_id":"p2","quote":"Allocation concealed"}],"expand":{"keywords":[],"section_priors":[],"queries":[]}}',
        ]
    )
    state = {
        "question_set": question_set.model_dump(),
        "doc_structure": {
            "body": "",
            "sections": [
                {
                    "paragraph_id": "p1",
                    "title": "Background",
                    "page": 1,
                    "text": "No relevant information here.",
                },
                {
                    "paragraph_id": "p2",
                    "title": "Methods",
                    "page": 2,
                    "text": "Allocation concealed by sealed envelopes.",
                },
            ],
        },
        "llm_locator_mode": "llm",
        "llm_locator_llm": llm,
        "llm_locator_max_steps": 2,
        "llm_locator_seed_top_n": 1,
        "llm_locator_per_step_top_n": 2,
        "llm_locator_max_candidates": 5,
    }

    out = llm_locator_node(state)
    candidates = out["fulltext_candidates"]["q1"]
    assert any(item["paragraph_id"] == "p2" for item in candidates)


def test_llm_locator_node_respects_retry_ids() -> None:
    question_set = QuestionSet(
        version="test",
        variant="standard",
        questions=[
            Rob2Question(
                question_id="q1",
                rob2_id="q1",
                domain="D1",
                text="Question one",
                options=["Y", "N"],
                order=1,
            ),
            Rob2Question(
                question_id="q2",
                rob2_id="q2",
                domain="D1",
                text="Question two",
                options=["Y", "N"],
                order=2,
            ),
        ],
    )

    llm = _DummyLLM(
        content='{"sufficient":true,"evidence":[{"paragraph_id":"p1","quote":"random number table"}],"expand":{"keywords":[],"section_priors":[],"queries":[]}}'
    )
    prev_candidate = EvidenceCandidate(
        question_id="q2",
        paragraph_id="p2",
        title="Methods",
        page=1,
        text="Some previous evidence.",
        source="fulltext",
        score=1.0,
        supporting_quote="previous evidence",
        engine="llm_locator",
    ).model_dump()

    state = {
        "question_set": question_set.model_dump(),
        "doc_structure": {
            "body": "",
            "sections": [
                {
                    "paragraph_id": "p1",
                    "title": "Methods",
                    "page": 1,
                    "text": "Allocation used a random number table.",
                },
                {
                    "paragraph_id": "p2",
                    "title": "Methods",
                    "page": 1,
                    "text": "Some previous evidence.",
                },
            ],
        },
        "fulltext_candidates": {"q2": [prev_candidate]},
        "retry_question_ids": ["q1"],
        "llm_locator_mode": "llm",
        "llm_locator_llm": llm,
        "llm_locator_max_steps": 1,
        "llm_locator_seed_top_n": 1,
        "llm_locator_per_step_top_n": 1,
        "llm_locator_max_candidates": 5,
    }

    out = llm_locator_node(state)
    assert llm.invocations == 1
    assert out["fulltext_candidates"]["q2"] == [prev_candidate]
