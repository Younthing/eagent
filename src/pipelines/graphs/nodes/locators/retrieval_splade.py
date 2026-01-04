"""SPLADE-based retrieval locator with multi-query planning + RRF (Milestone 4/5)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

import numpy as np

from retrieval.engines.faiss_ip import build_ip_index, search_ip
from retrieval.engines.fusion import rrf_fuse
from retrieval.engines.splade import DEFAULT_SPLADE_MODEL_ID, get_splade_encoder
from retrieval.query_planning.llm import LLMQueryPlannerConfig, generate_query_plan_llm
from retrieval.query_planning.planner import generate_query_plan
from retrieval.rerankers.apply import apply_reranker
from retrieval.rerankers.cross_encoder import (
    DEFAULT_CROSS_ENCODER_MODEL_ID,
    get_cross_encoder_reranker,
)
from retrieval.structure.filters import filter_spans_by_section_priors
from rob2.locator_rules import get_locator_rules
from schemas.internal.documents import DocStructure
from schemas.internal.evidence import EvidenceBundle, EvidenceCandidate
from schemas.internal.rob2 import QuestionSet


_DEFAULT_QUERY_PLANNER_TEMPERATURE = 0.0
_DEFAULT_QUERY_PLANNER_MAX_RETRIES = 2
_DEFAULT_QUERY_PLANNER_MAX_KEYWORDS = 10
_DEFAULT_RERANKER_MAX_LENGTH = 512
_DEFAULT_RERANKER_BATCH_SIZE = 8
_DEFAULT_RERANKER_TOP_N = 50
_DEFAULT_SECTION_BONUS_WEIGHT = 0.25
_DEFAULT_SPLADE_QUERY_MAX = 64
_DEFAULT_SPLADE_DOC_MAX = 256
_DEFAULT_SPLADE_BATCH = 8


@dataclass(frozen=True)
class _StructuredFaissIndex:
    index: object
    mapping: List[int]  # local doc_index -> original span index
    section_scores: Dict[int, int]
    matched_priors: Dict[int, List[str]]
    fallback_used: bool
    priors_used: List[str]


def splade_retrieval_locator_node(state: dict) -> dict:
    """LangGraph node: run SPLADE retrieval with multi-query planning and RRF."""
    raw_doc = state.get("doc_structure")
    raw_questions = state.get("question_set")
    if raw_doc is None:
        raise ValueError("splade_retrieval_locator_node requires 'doc_structure'.")
    if raw_questions is None:
        raise ValueError("splade_retrieval_locator_node requires 'question_set'.")

    doc_structure = DocStructure.model_validate(raw_doc)
    question_set = QuestionSet.model_validate(raw_questions)

    rules = get_locator_rules()
    planner_requested = str(state.get("query_planner") or "deterministic").strip().lower()
    if planner_requested not in {"deterministic", "llm"}:
        raise ValueError("query_planner must be 'deterministic' or 'llm'")

    query_plan = generate_query_plan(question_set, rules, max_queries_per_question=5)
    planner_used = planner_requested
    planner_error: str | None = None
    planner_model: str | None = None
    planner_model_provider: str | None = None

    if planner_requested == "llm":
        planner_model = str(state.get("query_planner_model") or "").strip()
        planner_model_provider = state.get("query_planner_model_provider")
        temperature_raw = state.get("query_planner_temperature")
        planner_temperature = (
            _DEFAULT_QUERY_PLANNER_TEMPERATURE
            if temperature_raw is None
            else float(str(temperature_raw))
        )

        timeout_raw = state.get("query_planner_timeout")
        planner_timeout = None if timeout_raw is None else float(str(timeout_raw))

        max_tokens_raw = state.get("query_planner_max_tokens")
        planner_max_tokens = (
            None if max_tokens_raw is None else int(str(max_tokens_raw))
        )

        max_retries_raw = state.get("query_planner_max_retries")
        planner_max_retries = (
            _DEFAULT_QUERY_PLANNER_MAX_RETRIES
            if max_retries_raw is None
            else int(str(max_retries_raw))
        )

        max_keywords_raw = state.get("query_planner_max_keywords")
        max_keywords = (
            _DEFAULT_QUERY_PLANNER_MAX_KEYWORDS
            if max_keywords_raw is None
            else int(str(max_keywords_raw))
        )

        if not planner_model:
            planner_used = "deterministic"
            planner_error = (
                "Missing query planner model (set QUERY_PLANNER_MODEL or state['query_planner_model'])."
            )
        else:
            config = LLMQueryPlannerConfig(
                model=planner_model,
                model_provider=str(planner_model_provider)
                if planner_model_provider
                else None,
                temperature=planner_temperature,
                timeout=planner_timeout,
                max_tokens=planner_max_tokens,
                max_retries=planner_max_retries,
            )
            try:
                query_plan = generate_query_plan_llm(
                    question_set,
                    rules,
                    config=config,
                    max_queries_per_question=5,
                    max_keywords_per_question=max_keywords,
                )
            except Exception as exc:
                planner_used = "deterministic"
                planner_error = f"{type(exc).__name__}: {exc}"

    reranker_requested = str(state.get("reranker") or "none").strip().lower()
    reranker_requested = reranker_requested.replace("-", "_")
    if reranker_requested not in {"none", "cross_encoder"}:
        raise ValueError("reranker must be 'none' or 'cross_encoder'")

    reranker_used = reranker_requested
    reranker_error: str | None = None
    reranker_model_id: str | None = None
    reranker_device: str | None = None
    reranker_max_length: int | None = None
    reranker_batch_size: int | None = None
    reranker_top_n: int | None = None
    cross_encoder = None

    if reranker_requested == "cross_encoder":
        reranker_model_id = str(
            state.get("reranker_model_id") or DEFAULT_CROSS_ENCODER_MODEL_ID
        ).strip()
        reranker_device = (
            str(state.get("reranker_device")).strip()
            if state.get("reranker_device") is not None
            else None
        )
        reranker_max_length = int(
            state.get("reranker_max_length") or _DEFAULT_RERANKER_MAX_LENGTH
        )
        reranker_batch_size = int(
            state.get("reranker_batch_size") or _DEFAULT_RERANKER_BATCH_SIZE
        )
        reranker_top_n = int(state.get("rerank_top_n") or _DEFAULT_RERANKER_TOP_N)

        if reranker_max_length < 1:
            raise ValueError("reranker_max_length must be >= 1")
        if reranker_batch_size < 1:
            raise ValueError("reranker_batch_size must be >= 1")
        if reranker_top_n < 1:
            raise ValueError("rerank_top_n must be >= 1")

        try:
            cross_encoder = get_cross_encoder_reranker(
                model_id=reranker_model_id,
                device=reranker_device,
            )
        except Exception as exc:
            reranker_used = "none"
            reranker_error = f"{type(exc).__name__}: {exc}"

    top_k = int(state.get("top_k") or rules.defaults.top_k)
    per_query_top_n = int(state.get("per_query_top_n") or 50)
    rrf_k = int(state.get("rrf_k") or 60)
    use_structure = bool(state.get("use_structure", False))
    section_bonus_weight = float(state.get("section_bonus_weight", _DEFAULT_SECTION_BONUS_WEIGHT))
    if section_bonus_weight < 0:
        raise ValueError("section_bonus_weight must be >= 0")

    model_id = str(
        state.get("splade_model_id") or DEFAULT_SPLADE_MODEL_ID
    ).strip()
    device = (
        str(state.get("splade_device")).strip()
        if state.get("splade_device") is not None
        else None
    )
    hf_token = state.get("splade_hf_token")
    query_max_length = int(
        state.get("splade_query_max_length") or _DEFAULT_SPLADE_QUERY_MAX
    )
    doc_max_length = int(
        state.get("splade_doc_max_length") or _DEFAULT_SPLADE_DOC_MAX
    )
    batch_size = int(state.get("splade_batch_size") or _DEFAULT_SPLADE_BATCH)

    spans = doc_structure.sections
    if not spans:
        return {
            "splade_queries": query_plan,
            "splade_query_planner": {
                "requested": planner_requested,
                "used": planner_used,
                "model": planner_model,
                "model_provider": planner_model_provider,
                "error": planner_error,
            },
            "splade_reranker": {
                "requested": reranker_requested,
                "used": reranker_used,
                "model_id": reranker_model_id,
                "device": cross_encoder.device if cross_encoder is not None else None,
                "top_n": reranker_top_n,
                "max_length": reranker_max_length,
                "batch_size": reranker_batch_size,
                "error": reranker_error,
            },
            "splade_rankings": {},
            "splade_candidates": {},
            "splade_evidence": [],
            "splade_rules_version": rules.version,
            "splade_config": {
                "model_id": model_id,
                "device": str(device) if device else None,
                "top_k": top_k,
                "per_query_top_n": per_query_top_n,
                "rrf_k": rrf_k,
                "use_structure": use_structure,
                "section_bonus_weight": section_bonus_weight,
                "doc_max_length": doc_max_length,
                "query_max_length": query_max_length,
                "batch_size": batch_size,
                "index_size": 0,
            },
            "splade_structure": {} if use_structure else None,
        }

    encoder = get_splade_encoder(model_id=model_id, device=device, hf_token=hf_token)

    doc_vectors = encoder.encode(
        [span.text for span in spans],
        max_length=doc_max_length,
        batch_size=batch_size,
    )
    if doc_vectors.shape[0] != len(spans):
        raise RuntimeError("SPLADE doc embedding count mismatch.")

    full_index = build_ip_index(doc_vectors)
    full_mapping = list(range(len(spans)))

    domain_indices: Dict[str, _StructuredFaissIndex] = {}
    if use_structure:
        for domain, domain_rules in rules.domains.items():
            priors = domain_rules.section_priors
            filtered = filter_spans_by_section_priors(spans, priors)
            if filtered.indices:
                domain_indices[domain] = _StructuredFaissIndex(
                    index=build_ip_index(doc_vectors[filtered.indices]),
                    mapping=filtered.indices,
                    section_scores=filtered.section_scores,
                    matched_priors=filtered.matched_priors,
                    fallback_used=False,
                    priors_used=list(priors),
                )
            else:
                domain_indices[domain] = _StructuredFaissIndex(
                    index=full_index,
                    mapping=full_mapping,
                    section_scores={},
                    matched_priors={},
                    fallback_used=True,
                    priors_used=list(priors),
                )

    rankings: Dict[str, Dict[str, List[Tuple[int, float]]]] = {}
    candidates_by_q: Dict[str, List[EvidenceCandidate]] = {}
    bundles: List[EvidenceBundle] = []
    structure_debug: Dict[str, dict] = {}

    for question in question_set.questions:
        question_id = question.question_id
        queries = query_plan.get(question_id) or []

        selected = _StructuredFaissIndex(
            index=full_index,
            mapping=full_mapping,
            section_scores={},
            matched_priors={},
            fallback_used=False,
            priors_used=[],
        )
        if use_structure:
            override = rules.question_overrides.get(question_id)
            priors_used = list(rules.domains[question.domain].section_priors)
            if override and override.section_priors:
                priors_used = _merge_unique(priors_used, override.section_priors)
                filtered = filter_spans_by_section_priors(spans, priors_used)
                if filtered.indices:
                    selected = _StructuredFaissIndex(
                        index=build_ip_index(doc_vectors[filtered.indices]),
                        mapping=filtered.indices,
                        section_scores=filtered.section_scores,
                        matched_priors=filtered.matched_priors,
                        fallback_used=False,
                        priors_used=priors_used,
                    )
                else:
                    selected = _StructuredFaissIndex(
                        index=full_index,
                        mapping=full_mapping,
                        section_scores={},
                        matched_priors={},
                        fallback_used=True,
                        priors_used=priors_used,
                    )
            else:
                selected = domain_indices.get(question.domain) or selected

        per_query: Dict[str, List[Tuple[int, float]]] = {}
        for query in queries:
            query_vec = encoder.encode([query], max_length=query_max_length)
            scores, local_indices = search_ip(
                selected.index, query_vec, top_n=per_query_top_n
            )
            per_query[query] = _rank_faiss_hits(
                scores=scores,
                indices=local_indices,
                mapping=selected.mapping,
                section_scores=selected.section_scores,
                section_bonus_weight=section_bonus_weight,
            )

        rankings[question_id] = per_query

        fused = rrf_fuse(per_query, k=rrf_k) if per_query else []
        candidates: List[EvidenceCandidate] = []
        for rank, hit in enumerate(fused, start=1):
            span = spans[hit.doc_index]
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
                    engine="splade",
                    engine_score=hit.best_engine_score,
                    rrf_score=hit.rrf_score,
                    retrieval_rank=rank,
                    query_ranks=hit.query_ranks or None,
                    section_score=float(selected.section_scores.get(hit.doc_index, 0)),
                    matched_section_priors=selected.matched_priors.get(hit.doc_index),
                )
            )

        if cross_encoder is not None and candidates:
            candidates = apply_reranker(
                reranker=cross_encoder,
                query=question.text,
                candidates=candidates,
                top_n=min(reranker_top_n or len(candidates), len(candidates)),
                max_length=reranker_max_length or 512,
                batch_size=reranker_batch_size or 8,
            )

        candidates_by_q[question_id] = candidates
        bundles.append(EvidenceBundle(question_id=question_id, items=candidates[:top_k]))

        if use_structure:
            structure_debug[question_id] = {
                "domain": question.domain,
                "filtered_span_count": len(selected.mapping)
                if not selected.fallback_used
                else 0,
                "total_span_count": len(spans),
                "fallback_used": selected.fallback_used,
                "section_priors": selected.priors_used,
            }

    return {
        "splade_queries": query_plan,
        "splade_query_planner": {
            "requested": planner_requested,
            "used": planner_used,
            "model": planner_model,
            "model_provider": planner_model_provider,
            "error": planner_error,
        },
        "splade_reranker": {
            "requested": reranker_requested,
            "used": reranker_used,
            "model_id": reranker_model_id,
            "device": cross_encoder.device if cross_encoder is not None else None,
            "top_n": reranker_top_n,
            "max_length": reranker_max_length,
            "batch_size": reranker_batch_size,
            "error": reranker_error,
        },
        "splade_rankings": {
            question_id: {
                query: [
                    {
                        "paragraph_id": spans[doc_index].paragraph_id,
                        "score": score,
                    }
                    for doc_index, score in hits
                ]
                for query, hits in per_query.items()
            }
            for question_id, per_query in rankings.items()
        },
        "splade_candidates": {
            question_id: [candidate.model_dump() for candidate in candidates]
            for question_id, candidates in candidates_by_q.items()
        },
        "splade_evidence": [bundle.model_dump() for bundle in bundles],
        "splade_rules_version": rules.version,
        "splade_config": {
            "model_id": model_id,
            "device": encoder.device,
            "top_k": top_k,
            "per_query_top_n": per_query_top_n,
            "rrf_k": rrf_k,
            "use_structure": use_structure,
            "section_bonus_weight": section_bonus_weight,
            "doc_max_length": doc_max_length,
            "query_max_length": query_max_length,
            "batch_size": batch_size,
            "index_size": len(spans),
            "vector_dim": int(doc_vectors.shape[1]),
        },
        "splade_structure": structure_debug if use_structure else None,
    }


def _merge_unique(base: List[str], extra: List[str]) -> List[str]:
    seen: set[str] = set()
    merged: List[str] = []
    for item in base + extra:
        cleaned = item.strip()
        if not cleaned:
            continue
        key = cleaned.casefold()
        if key in seen:
            continue
        seen.add(key)
        merged.append(cleaned)
    return merged


def _rank_faiss_hits(
    *,
    scores: np.ndarray,
    indices: np.ndarray,
    mapping: List[int],
    section_scores: Dict[int, int],
    section_bonus_weight: float,
) -> List[Tuple[int, float]]:
    if scores.size == 0 or indices.size == 0:
        return []

    score_row = scores[0]
    index_row = indices[0]
    ranked: List[Tuple[int, float, float]] = []
    for local_idx, raw_score in zip(index_row.tolist(), score_row.tolist(), strict=False):
        if local_idx < 0:
            continue
        original_index = mapping[int(local_idx)]
        section_score = section_scores.get(original_index, 0)
        composite = float(raw_score) + section_score * section_bonus_weight
        ranked.append((original_index, float(raw_score), composite))

    ranked.sort(key=lambda item: (-item[2], -item[1], item[0]))
    return [(doc_index, raw_score) for doc_index, raw_score, _ in ranked]


__all__ = ["splade_retrieval_locator_node"]
