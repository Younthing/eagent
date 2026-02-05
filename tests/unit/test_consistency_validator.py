from __future__ import annotations

from typing import cast

from evidence.validators.consistency import ChatModelLike, judge_consistency
from schemas.internal.evidence import EvidenceSupport, FusedEvidenceCandidate


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


def _candidate(question_id: str, paragraph_id: str, text: str) -> FusedEvidenceCandidate:
    return FusedEvidenceCandidate(
        question_id=question_id,
        paragraph_id=paragraph_id,
        title="Methods",
        page=1,
        text=text,
        fusion_score=0.5,
        fusion_rank=1,
        support_count=1,
        supports=[EvidenceSupport(engine="bm25", rank=1, score=1.0, query="randomization")],
    )


def test_judge_consistency_parses_json_with_noise() -> None:
    llm = _DummyLLM(
        content=(
            "noise {bad}\n"
            '{"label":"pass","confidence":0.9,"conflicts":[]}'
        )
    )
    candidates = [
        _candidate("q1", "p1", "Allocation used a random number table."),
        _candidate("q1", "p2", "Randomization used sealed envelopes."),
    ]

    verdict = judge_consistency(
        "Was the allocation sequence random?",
        candidates,
        llm=cast(ChatModelLike, llm),
    )

    assert verdict.label == "pass"
    assert llm.invocations == 1
