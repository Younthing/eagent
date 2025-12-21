"""Deterministic multi-query planner for retrieval (Milestone 4)."""

from __future__ import annotations

from typing import Dict, Iterable, List

from schemas.internal.locator import LocatorRules
from schemas.internal.rob2 import QuestionSet, Rob2Question


def generate_query_plan(
    question_set: QuestionSet,
    rules: LocatorRules,
    *,
    max_queries_per_question: int = 5,
    max_keywords_per_combined_query: int = 8,
    max_single_keyword_queries: int = 3,
) -> Dict[str, List[str]]:
    """Generate deterministic queries per question_id."""
    return {
        question.question_id: generate_queries_for_question(
            question,
            rules,
            max_queries=max_queries_per_question,
            max_keywords_per_combined_query=max_keywords_per_combined_query,
            max_single_keyword_queries=max_single_keyword_queries,
        )
        for question in question_set.questions
    }


def generate_queries_for_question(
    question: Rob2Question,
    rules: LocatorRules,
    *,
    max_queries: int = 5,
    max_keywords_per_combined_query: int = 8,
    max_single_keyword_queries: int = 3,
) -> List[str]:
    """Generate a small, stable set of query strings for a question."""
    if max_queries < 1:
        raise ValueError("max_queries must be >= 1")

    override = rules.question_overrides.get(question.question_id)
    keyword_phrases = _merge_unique(
        override.keywords if override and override.keywords else [],
        rules.domains[question.domain].keywords,
    )

    combined = " ".join(keyword_phrases[:max_keywords_per_combined_query]).strip()
    single_queries = keyword_phrases[:max_single_keyword_queries]

    candidates = [question.text, *single_queries]
    if combined:
        candidates.append(combined)
    candidates.extend(keyword_phrases[max_single_keyword_queries:])

    deduped = _dedupe_preserve_order(
        query.strip() for query in candidates if isinstance(query, str) and query.strip()
    )
    return deduped[:max_queries]


def _merge_unique(a: Iterable[str], b: Iterable[str]) -> List[str]:
    seen: set[str] = set()
    merged: List[str] = []
    for item in list(a) + list(b):
        cleaned = item.strip()
        if not cleaned:
            continue
        key = cleaned.casefold()
        if key in seen:
            continue
        seen.add(key)
        merged.append(cleaned)
    return merged


def _dedupe_preserve_order(items: Iterable[str]) -> List[str]:
    seen: set[str] = set()
    result: List[str] = []
    for item in items:
        key = item.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


__all__ = ["generate_query_plan", "generate_queries_for_question"]

