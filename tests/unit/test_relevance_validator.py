from __future__ import annotations

from typing import cast

from evidence.validators.relevance import ChatModelLike, annotate_relevance
from pipelines.graphs.nodes.validators.relevance import relevance_validator_node
from schemas.internal.evidence import EvidenceSupport, FusedEvidenceCandidate, RelevanceVerdict
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


def _candidate(*, text: str) -> FusedEvidenceCandidate:
    return FusedEvidenceCandidate(
        question_id="q1_1",
        paragraph_id="p1",
        title="Methods",
        page=2,
        text=text,
        fusion_score=0.03,
        fusion_rank=1,
        support_count=1,
        supports=[
            EvidenceSupport(engine="bm25", rank=1, score=1.0, query="random number table")
        ],
    )


def _candidate_for(question_id: str, paragraph_id: str, text: str) -> FusedEvidenceCandidate:
    return FusedEvidenceCandidate(
        question_id=question_id,
        paragraph_id=paragraph_id,
        title="Methods",
        page=2,
        text=text,
        fusion_score=0.03,
        fusion_rank=1,
        support_count=1,
        supports=[
            EvidenceSupport(engine="bm25", rank=1, score=1.0, query="random number table")
        ],
    )


def test_annotate_relevance_parses_json_and_keeps_relevant_label() -> None:
    llm = _DummyLLM(
        content='{"label":"relevant","confidence":0.9,"supporting_quote":"random number table"}'
    )
    candidates = annotate_relevance(
        "Was the allocation sequence random?",
        [_candidate(text="Allocation used a random number table.")],
        llm=cast(ChatModelLike, llm),
    )

    assert llm.invocations == 1
    assert candidates[0].relevance is not None
    assert candidates[0].relevance.label == "relevant"
    assert candidates[0].relevance.supporting_quote == "random number table"


def test_annotate_relevance_require_quote_downgrades_missing_quote_to_unknown() -> None:
    llm = _DummyLLM(
        content='{"label":"relevant","confidence":0.9,"supporting_quote":"sealed envelopes"}'
    )
    candidates = annotate_relevance(
        "Was the allocation sequence random?",
        [_candidate(text="Allocation used a random number table.")],
        llm=cast(ChatModelLike, llm),
    )

    assert candidates[0].relevance is not None
    assert candidates[0].relevance.label == "unknown"


def test_relevance_validator_node_selects_passed_candidates_and_falls_back() -> None:
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

    llm = _DummyLLM(
        content='{"label":"irrelevant","confidence":0.8,"supporting_quote":null}'
    )
    state = {
        "question_set": question_set.model_dump(),
        "fusion_candidates": {"q1_1": [_candidate(text="Baseline characteristics.").model_dump()]},
        "relevance_mode": "llm",
        "relevance_llm": cast(ChatModelLike, llm),
        "relevance_top_k": 1,
        "relevance_top_n": 1,
        "relevance_min_confidence": 0.6,
        "relevance_require_quote": True,
        "relevance_fill_to_top_k": True,
    }
    out = relevance_validator_node(state)

    assert out["relevance_debug"]["q1_1"]["fallback_used"] is True
    bundles = out["relevance_evidence"]
    assert len(bundles) == 1
    assert bundles[0]["question_id"] == "q1_1"
    assert len(bundles[0]["items"]) == 1


def test_relevance_validator_node_merges_retry_questions() -> None:
    question_set = QuestionSet(
        version="test",
        variant="standard",
        questions=[
            Rob2Question(
                question_id="q1_1",
                rob2_id="q1_1",
                domain="D1",
                text="Question one",
                options=["Y", "PY", "PN", "N", "NI"],
                order=1,
            ),
            Rob2Question(
                question_id="q2_1",
                rob2_id="q2_1",
                domain="D1",
                text="Question two",
                options=["Y", "PY", "PN", "N", "NI"],
                order=2,
            ),
        ],
    )

    prev_candidate = _candidate_for("q2_1", "p_prev", "Previous evidence.")
    prev_bundle = {
        "question_id": "q2_1",
        "items": [prev_candidate.model_dump()],
    }

    state = {
        "question_set": question_set.model_dump(),
        "fusion_candidates": {
            "q1_1": [_candidate_for("q1_1", "p1", "New evidence.").model_dump()]
        },
        "relevance_candidates": {"q2_1": [prev_candidate.model_dump()]},
        "relevance_evidence": [prev_bundle],
        "relevance_mode": "none",
        "relevance_top_k": 1,
        "relevance_top_n": 1,
        "retry_question_ids": ["q1_1"],
    }

    out = relevance_validator_node(state)

    assert out["relevance_candidates"]["q2_1"] == [prev_candidate.model_dump()]
    assert any(bundle["question_id"] == "q2_1" for bundle in out["relevance_evidence"])


def test_relevance_validator_preserves_existing_relevance() -> None:
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

    candidate = _candidate(text="Allocation used a random number table.")
    candidate = candidate.model_copy(
        update={
            "relevance": RelevanceVerdict(
                label="relevant",
                confidence=1.0,
                supporting_quote="random number table",
            )
        }
    )
    state = {
        "question_set": question_set.model_dump(),
        "fusion_candidates": {"q1_1": [candidate.model_dump()]},
        "relevance_mode": "none",
        "relevance_top_k": 1,
        "relevance_top_n": 1,
    }

    out = relevance_validator_node(state)
    updated = out["relevance_candidates"]["q1_1"][0]
    assert updated["relevance"]["label"] == "relevant"
    assert updated["relevance"]["supporting_quote"] == "random number table"
