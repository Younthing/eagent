from __future__ import annotations

from evidence.fusion import fuse_candidates_for_question
from pipelines.graphs.nodes.fusion import fusion_node
from schemas.internal.evidence import EvidenceCandidate
from schemas.internal.rob2 import QuestionSet, Rob2Question


def _rb(question_id: str, paragraph_id: str, score: float) -> EvidenceCandidate:
    return EvidenceCandidate(
        question_id=question_id,
        paragraph_id=paragraph_id,
        title="Methods",
        page=2,
        text=f"rb {paragraph_id}",
        source="rule_based",
        score=score,
    )


def _bm25(question_id: str, paragraph_id: str, score: float, *, query: str) -> EvidenceCandidate:
    return EvidenceCandidate(
        question_id=question_id,
        paragraph_id=paragraph_id,
        title="Methods",
        page=2,
        text=f"bm25 {paragraph_id}",
        source="retrieval",
        score=score,
        engine="bm25",
        query=query,
        rrf_score=score,
        retrieval_rank=1,
    )


def test_fuse_candidates_boosts_multi_engine_hits() -> None:
    question_id = "q1_1"
    fused = fuse_candidates_for_question(
        question_id,
        candidates_by_engine={
            "rule_based": [_rb(question_id, "p1", 10.0), _rb(question_id, "p2", 9.0)],
            "bm25": [_bm25(question_id, "p1", 0.03, query="random number sequence")],
        },
        rrf_k=60,
    )

    assert fused
    assert fused[0].paragraph_id == "p1"
    assert fused[0].support_count == 2
    assert {support.engine for support in fused[0].supports} == {"rule_based", "bm25"}


def test_fusion_node_returns_full_candidates_and_top_k_bundles() -> None:
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
    state = {
        "question_set": question_set.model_dump(),
        "top_k": 1,
        "rule_based_candidates": {
            "q1_1": [
                _rb("q1_1", "p1", 10.0).model_dump(),
            ]
        },
        "bm25_candidates": {
            "q1_1": [
                _bm25("q1_1", "p1", 0.03, query="random number sequence").model_dump(),
                _bm25("q1_1", "p3", 0.02, query="randomization").model_dump(),
            ]
        },
    }
    out = fusion_node(state)

    candidates = out["fusion_candidates"]["q1_1"]
    assert len(candidates) == 2
    assert candidates[0]["paragraph_id"] == "p1"
    assert {support["engine"] for support in candidates[0]["supports"]} == {
        "rule_based",
        "bm25",
    }

    bundles = out["fusion_evidence"]
    assert len(bundles) == 1
    assert bundles[0]["question_id"] == "q1_1"
    assert len(bundles[0]["items"]) == 1
    assert bundles[0]["items"][0]["paragraph_id"] == "p1"

