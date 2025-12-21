"""BM25-based retrieval locator with multi-query planning + RRF (Milestone 4)."""

from __future__ import annotations

from typing import Dict, List, Tuple

from retrieval.engines.bm25 import build_bm25_index
from retrieval.engines.fusion import rrf_fuse
from retrieval.query_planning.planner import generate_query_plan
from rob2.locator_rules import get_locator_rules
from schemas.internal.documents import DocStructure
from schemas.internal.evidence import EvidenceBundle, EvidenceCandidate
from schemas.internal.rob2 import QuestionSet


def bm25_retrieval_locator_node(state: dict) -> dict:
    """LangGraph node: run BM25 retrieval with multi-query planning and RRF."""
    raw_doc = state.get("doc_structure")
    raw_questions = state.get("question_set")
    if raw_doc is None:
        raise ValueError("bm25_retrieval_locator_node requires 'doc_structure'.")
    if raw_questions is None:
        raise ValueError("bm25_retrieval_locator_node requires 'question_set'.")

    doc_structure = DocStructure.model_validate(raw_doc)
    question_set = QuestionSet.model_validate(raw_questions)

    rules = get_locator_rules()
    query_plan = generate_query_plan(question_set, rules, max_queries_per_question=5)

    top_k = int(state.get("top_k") or rules.defaults.top_k)
    per_query_top_n = int(state.get("per_query_top_n") or 50)
    rrf_k = int(state.get("rrf_k") or 60)

    index = build_bm25_index(doc_structure.sections)

    rankings: Dict[str, Dict[str, List[Tuple[int, float]]]] = {}
    candidates_by_q: Dict[str, List[EvidenceCandidate]] = {}
    bundles: List[EvidenceBundle] = []

    for question_id, queries in query_plan.items():
        per_query: Dict[str, List[Tuple[int, float]]] = {}
        for query in queries:
            hits = index.search(query, top_n=per_query_top_n)
            per_query[query] = [(hit.doc_index, hit.score) for hit in hits]

        rankings[question_id] = per_query

        fused = rrf_fuse(per_query, k=rrf_k) if per_query else []
        candidates: List[EvidenceCandidate] = []
        for rank, hit in enumerate(fused, start=1):
            span = doc_structure.sections[hit.doc_index]
            candidates.append(
                EvidenceCandidate(
                    question_id=question_id,
                    paragraph_id=span.paragraph_id,
                    title=span.title,
                    page=span.page,
                    text=span.text,
                    source="retrieval",
                    score=hit.rrf_score,
                    query=hit.best_query or None,
                    bm25_score=hit.best_engine_score,
                    rrf_score=hit.rrf_score,
                    retrieval_rank=rank,
                    query_ranks=hit.query_ranks or None,
                )
            )

        candidates_by_q[question_id] = candidates
        bundles.append(
            EvidenceBundle(question_id=question_id, items=candidates[:top_k])
        )

    return {
        "bm25_queries": query_plan,
        "bm25_rankings": {
            question_id: {
                query: [
                    {
                        "paragraph_id": doc_structure.sections[doc_index].paragraph_id,
                        "score": score,
                    }
                    for doc_index, score in hits
                ]
                for query, hits in per_query.items()
            }
            for question_id, per_query in rankings.items()
        },
        "bm25_candidates": {
            question_id: [candidate.model_dump() for candidate in candidates]
            for question_id, candidates in candidates_by_q.items()
        },
        "bm25_evidence": [bundle.model_dump() for bundle in bundles],
        "bm25_rules_version": rules.version,
        "bm25_config": {
            "top_k": top_k,
            "per_query_top_n": per_query_top_n,
            "rrf_k": rrf_k,
            "index_size": index.size,
        },
    }


__all__ = ["bm25_retrieval_locator_node"]

