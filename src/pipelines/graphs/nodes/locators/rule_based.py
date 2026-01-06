"""Rule-based evidence locator (Milestone 3)."""

from __future__ import annotations

import re
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from rob2.locator_rules import get_locator_rules
from retrieval.tokenization import normalize_for_match
from schemas.internal.documents import DocStructure, SectionSpan
from schemas.internal.evidence import EvidenceBundle, EvidenceCandidate
from schemas.internal.locator import LocatorRules
from schemas.internal.rob2 import QuestionSet, Rob2Question


def rule_based_locator_node(state: dict) -> dict:
    """LangGraph node: emit rule-based evidence candidates and top-k bundles."""
    raw_doc = state.get("doc_structure")
    raw_questions = state.get("question_set")
    if raw_doc is None:
        raise ValueError("rule_based_locator_node requires 'doc_structure'.")
    if raw_questions is None:
        raise ValueError("rule_based_locator_node requires 'question_set'.")

    doc_structure = DocStructure.model_validate(raw_doc)
    question_set = QuestionSet.model_validate(raw_questions)
    rules = get_locator_rules()

    top_k = state.get("top_k") or rules.defaults.top_k
    candidates_by_q, bundles = rule_based_locate(
        doc_structure,
        question_set,
        rules,
        top_k=top_k,
    )

    return {
        "rule_based_candidates": {
            question_id: [candidate.model_dump() for candidate in candidates]
            for question_id, candidates in candidates_by_q.items()
        },
        "rule_based_evidence": [bundle.model_dump() for bundle in bundles],
        "rule_based_rules_version": rules.version,
    }


def rule_based_locate(
    doc_structure: DocStructure,
    question_set: QuestionSet,
    rules: LocatorRules,
    *,
    top_k: int,
) -> Tuple[Dict[str, List[EvidenceCandidate]], List[EvidenceBundle]]:
    """Locate evidence for each question via section/keyword heuristics."""
    candidates_by_q: Dict[str, List[EvidenceCandidate]] = {}
    bundles: List[EvidenceBundle] = []

    for question in question_set.questions:
        candidates = _locate_for_question(doc_structure.sections, question, rules)
        candidates_by_q[question.question_id] = candidates
        bundles.append(
            EvidenceBundle(
                question_id=question.question_id,
                items=candidates[:top_k],
            )
        )

    return candidates_by_q, bundles


def _locate_for_question(
    spans: Sequence[SectionSpan],
    question: Rob2Question,
    rules: LocatorRules,
) -> List[EvidenceCandidate]:
    section_priors, keywords = _effective_rules(question, rules)

    ranked: List[Tuple[int, EvidenceCandidate]] = []
    for position, span in enumerate(spans):
        section_score, matched_priors = _score_section(span.title, section_priors)
        matched_keywords = _match_keywords(span.text, keywords)
        keyword_score = float(len(matched_keywords))
        if section_score == 0 and keyword_score == 0:
            continue

        score = float(section_score) * 10.0 + keyword_score
        ranked.append(
            (
                position,
                EvidenceCandidate(
                    question_id=question.question_id,
                    paragraph_id=span.paragraph_id,
                    title=span.title,
                    page=span.page,
                    text=span.text,
                    source="rule_based",
                    score=score,
                    section_score=float(section_score),
                    keyword_score=keyword_score,
                    matched_keywords=matched_keywords or None,
                    matched_section_priors=matched_priors or None,
                ),
            )
        )

    ranked.sort(
        key=lambda item: (
            -item[1].score,
            item[1].page if item[1].page is not None else 10_000,
            item[0],
        )
    )
    return [candidate for _, candidate in ranked]


def _effective_rules(
    question: Rob2Question,
    rules: LocatorRules,
) -> Tuple[List[str], List[str]]:
    domain_rules = rules.domains[question.domain]
    override = rules.question_overrides.get(question.question_id)

    section_priors = _merge_unique(
        domain_rules.section_priors,
        override.section_priors if override else None,
    )
    keywords = _merge_unique(
        domain_rules.keywords,
        override.keywords if override else None,
    )
    return section_priors, keywords


def _merge_unique(base: Iterable[str], extra: Optional[Iterable[str]]) -> List[str]:
    result: List[str] = []
    seen: set[str] = set()

    for item in list(base) + list(extra or []):
        cleaned = item.strip()
        if not cleaned:
            continue
        key = cleaned.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(cleaned)

    return result


def _normalize_for_match(text: str) -> str:
    return normalize_for_match(text)


def _score_section(title: str, priors: Sequence[str]) -> Tuple[int, List[str]]:
    if not priors:
        return 0, []

    normalized_title = _normalize_for_match(title)
    if not normalized_title:
        return 0, []

    matched: List[str] = []
    score = 0
    for index, prior in enumerate(priors):
        needle = _normalize_for_match(prior)
        if not needle:
            continue
        if needle in normalized_title:
            matched.append(prior)
            score = max(score, len(priors) - index)

    return score, matched


def _match_keywords(text: str, keywords: Sequence[str]) -> List[str]:
    if not keywords:
        return []

    haystack = _normalize_for_match(text)
    if not haystack:
        return []

    matched: List[str] = []
    seen: set[str] = set()

    for keyword in keywords:
        needle = _normalize_for_match(keyword)
        if not needle:
            continue

        hit = False
        if _is_short_token(needle):
            if re.search(rf"\b{re.escape(needle)}\b", haystack):
                hit = True
        else:
            if needle in haystack:
                hit = True

        if hit:
            key = keyword.casefold()
            if key not in seen:
                seen.add(key)
                matched.append(keyword)

    return matched


def _is_short_token(token: str) -> bool:
    return token.isascii() and len(token) <= 4 and token.isalnum()


__all__ = ["rule_based_locate", "rule_based_locator_node"]
