"""ROB2 aggregator and final output formatter (Milestone 10)."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping, Sequence

from schemas.internal.decisions import DomainDecision
from schemas.internal.documents import DocStructure
from schemas.internal.locator import DomainId
from schemas.internal.results import (
    Citation,
    CitationUse,
    OverallRisk,
    Rob2AnswerResult,
    Rob2DomainResult,
    Rob2FinalOutput,
    Rob2OverallResult,
)
from schemas.internal.rob2 import QuestionSet, Rob2Question


_DOMAIN_ORDER: list[DomainId] = ["D1", "D2", "D3", "D4", "D5"]
_DOMAIN_LABELS: dict[DomainId, str] = {
    "D1": "Randomization process",
    "D2": "Deviations from intended interventions",
    "D3": "Missing outcome data",
    "D4": "Measurement of the outcome",
    "D5": "Selection of the reported result",
}


def aggregate_node(state: dict) -> dict:
    raw_doc = state.get("doc_structure")
    if raw_doc is None:
        raise ValueError("aggregate_node requires 'doc_structure'.")
    doc_structure = DocStructure.model_validate(raw_doc)

    raw_questions = state.get("question_set")
    if raw_questions is None:
        raise ValueError("aggregate_node requires 'question_set'.")
    question_set = QuestionSet.model_validate(raw_questions)

    decisions = _load_domain_decisions(state)
    questions_by_id = {q.question_id: q for q in question_set.questions}
    spans_by_pid = {span.paragraph_id: span for span in doc_structure.sections}

    citations_by_pid: Dict[str, Citation] = {}
    domain_results: List[Rob2DomainResult] = []

    for domain in _DOMAIN_ORDER:
        decision = decisions.get(domain)
        if decision is None:
            raise ValueError(f"Missing {domain} decision for aggregation.")

        answers = _sorted_answers(decision, questions_by_id)
        answer_results: List[Rob2AnswerResult] = []
        for answer in answers:
            question = questions_by_id.get(answer.question_id)
            answer_results.append(
                Rob2AnswerResult(
                    question_id=answer.question_id,
                    rob2_id=question.rob2_id if question else None,
                    text=question.text if question else None,
                    answer=answer.answer,
                    rationale=answer.rationale,
                    evidence_refs=answer.evidence_refs,
                    confidence=answer.confidence,
                )
            )
            for ref in answer.evidence_refs:
                pid = ref.paragraph_id
                citation = citations_by_pid.get(pid)
                if citation is None:
                    span = spans_by_pid.get(pid)
                    citation = Citation(
                        paragraph_id=pid,
                        page=span.page if span else ref.page,
                        title=span.title if span else ref.title,
                        text=span.text if span else None,
                        uses=[],
                    )
                    citations_by_pid[pid] = citation
                citation.uses.append(
                    CitationUse(domain=domain, question_id=answer.question_id, quote=ref.quote)
                )

        domain_results.append(
            Rob2DomainResult(
                domain=domain,
                effect_type=decision.effect_type,
                risk=decision.risk,
                risk_rationale=decision.risk_rationale,
                answers=answer_results,
                missing_questions=decision.missing_questions,
            )
        )

    overall_risk, overall_rationale = _compute_overall_risk(domain_results)
    final = Rob2FinalOutput(
        question_set_version=question_set.version,
        overall=Rob2OverallResult(risk=overall_risk, rationale=overall_rationale),
        domains=domain_results,
        citations=_sorted_citations(citations_by_pid.values()),
    )

    return {
        "rob2_result": final.model_dump(),
        "rob2_table_markdown": _format_markdown_table(final),
    }


def _load_domain_decisions(state: Mapping[str, Any]) -> dict[DomainId, DomainDecision]:
    mapping: dict[DomainId, DomainDecision] = {}
    for domain, key in (
        ("D1", "d1_decision"),
        ("D2", "d2_decision"),
        ("D3", "d3_decision"),
        ("D4", "d4_decision"),
        ("D5", "d5_decision"),
    ):
        raw = state.get(key)
        if raw is None:
            continue
        mapping[domain] = DomainDecision.model_validate(raw)
    return mapping


def _sorted_answers(
    decision: DomainDecision,
    questions_by_id: Mapping[str, Rob2Question],
) -> List[Any]:
    def key(item: Any) -> tuple[int, str]:
        question = questions_by_id.get(item.question_id)
        order = question.order if question else 10_000
        return order, item.question_id

    return sorted(decision.answers, key=key)


def _compute_overall_risk(
    domains: Sequence[Rob2DomainResult],
) -> tuple[OverallRisk, str]:
    # ROB2 overall judgement rule (Standard):
    # 1) If any domain is high -> overall high.
    # 2) If all domains are low -> overall low.
    # 3) Else if any domain is some concerns -> overall some concerns.
    # 4) If no domain results -> not_applicable.
    if not domains:
        return "not_applicable", "No domain assessments provided."

    risks = [domain.risk for domain in domains]
    if any(risk == "high" for risk in risks):
        highs = [domain.domain for domain in domains if domain.risk == "high"]
        return "high", f"Overall risk is high because {', '.join(highs)} is high."
    if all(risk == "low" for risk in risks):
        return "low", "Overall risk is low because all domains are low."
    concerns = [domain.domain for domain in domains if domain.risk == "some_concerns"]
    if concerns:
        return (
            "some_concerns",
            "Overall risk has some concerns because "
            f"{', '.join(concerns)} has some concerns.",
        )
    return "not_applicable", "No applicable domain assessments provided."


def _sorted_citations(items: Iterable[Citation]) -> List[Citation]:
    def key(item: Citation) -> tuple[int, str]:
        page = item.page if isinstance(item.page, int) else 10_000
        return page, item.paragraph_id

    return sorted(items, key=key)


def _format_markdown_table(output: Rob2FinalOutput) -> str:
    lines = [
        "| Domain | Effect type | Risk |",
        "|---|---|---|",
    ]
    for domain in output.domains:
        label = _DOMAIN_LABELS.get(domain.domain, domain.domain)
        effect = domain.effect_type or "-"
        lines.append(f"| {domain.domain} ({label}) | {effect} | {domain.risk} |")
    lines.append(f"| Overall | - | {output.overall.risk} |")
    return "\n".join(lines)


__all__ = ["aggregate_node"]
