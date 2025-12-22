from __future__ import annotations

from typing import Sequence

from retrieval.rerankers.apply import apply_reranker
from retrieval.rerankers.contracts import RerankResult
from schemas.internal.documents import DocStructure, SectionSpan
from schemas.internal.evidence import EvidenceCandidate
from schemas.internal.rob2 import QuestionSet, Rob2Question


class _DummyReranker:
    name = "cross_encoder"
    device = "cpu"

    def rerank(
        self,
        query: str,
        passages: Sequence[str],
        *,
        max_length: int = 512,
        batch_size: int = 8,
    ) -> RerankResult:
        scores = [0.9 if "methods" in passage.casefold() else 0.1 for passage in passages]
        order = sorted(range(len(scores)), key=lambda idx: (-scores[idx], idx))
        return RerankResult(scores=scores, order=order)


def test_apply_reranker_reorders_and_adds_scores() -> None:
    candidates = [
        EvidenceCandidate(
            question_id="q1_1",
            paragraph_id="p1",
            title="Discussion",
            page=4,
            text="randomization randomization",
            source="retrieval",
            score=0.01,
            retrieval_rank=1,
            rrf_score=0.01,
        ),
        EvidenceCandidate(
            question_id="q1_1",
            paragraph_id="p2",
            title="Methods",
            page=2,
            text="computer-generated random number sequence",
            source="retrieval",
            score=0.02,
            retrieval_rank=2,
            rrf_score=0.02,
        ),
    ]

    reranked = apply_reranker(
        reranker=_DummyReranker(),
        query="Was the allocation sequence random?",
        candidates=candidates,
        top_n=2,
        max_length=64,
        batch_size=2,
    )

    assert [candidate.paragraph_id for candidate in reranked] == ["p2", "p1"]
    assert reranked[0].reranker == "cross_encoder"
    assert reranked[0].rerank_rank == 1
    assert reranked[0].rerank_score == 0.9
    assert reranked[0].score == 0.9


def test_bm25_locator_can_apply_optional_reranker(monkeypatch) -> None:
    from pipelines.graphs.nodes.locators import retrieval_bm25

    def _fake_get_cross_encoder_reranker(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        return _DummyReranker()

    monkeypatch.setattr(
        retrieval_bm25, "get_cross_encoder_reranker", _fake_get_cross_encoder_reranker
    )

    doc = DocStructure(
        body="",
        sections=[
            SectionSpan(
                paragraph_id="p1",
                title="Methods",
                page=2,
                text="We used a computer-generated random number sequence for allocation.",
            ),
            SectionSpan(
                paragraph_id="p2",
                title="Discussion",
                page=6,
                text="randomization " * 20,
            ),
        ],
    )
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

    output = retrieval_bm25.bm25_retrieval_locator_node(
        {
            "doc_structure": doc.model_dump(),
            "question_set": question_set.model_dump(),
            "top_k": 2,
            "per_query_top_n": 10,
            "rrf_k": 60,
            "use_structure": False,
            "reranker": "cross_encoder",
            "reranker_model_id": "dummy",
            "rerank_top_n": 10,
        }
    )

    candidates = output["bm25_candidates"]["q1_1"]
    assert candidates[0]["paragraph_id"] == "p1"
    assert candidates[0]["reranker"] == "cross_encoder"
    assert candidates[0]["rerank_rank"] == 1
