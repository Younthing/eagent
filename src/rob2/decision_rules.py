"""Rule-based ROB2 domain risk decision trees."""

from __future__ import annotations

from typing import Mapping, Optional, Literal

from schemas.internal.decisions import AnswerOption, DomainRisk
from schemas.internal.locator import DomainId

EffectType = Literal["assignment", "adherence"]

YES = {"Y", "PY"}
NO = {"N", "PN"}
NO_INFO = {"NI"}
NA = {"NA"}
YES_OR_NI = YES | NO_INFO
NO_OR_NI = NO | NO_INFO
YES_OR_NI_OR_NA = YES_OR_NI | NA
NO_OR_NA = NO | NA


def evaluate_domain_risk(
    domain: DomainId,
    answers: Mapping[str, AnswerOption],
    *,
    effect_type: Optional[EffectType] = None,
) -> Optional[DomainRisk]:
    """Return rule-based domain risk, or None when no rule exists."""
    if domain == "D1":
        return _risk_d1(answers)
    if domain == "D2":
        if effect_type == "assignment":
            return _risk_d2_assignment(answers)
        if effect_type == "adherence":
            return _risk_d2_adherence(answers)
        return None
    if domain == "D3":
        return _risk_d3(answers)
    if domain == "D4":
        return _risk_d4(answers)
    if domain == "D5":
        return _risk_d5(answers)
    return None


def _answer(answers: Mapping[str, AnswerOption], question_id: str) -> AnswerOption:
    return answers.get(question_id, "NI")


def _risk_d1(answers: Mapping[str, AnswerOption]) -> DomainRisk:
    q1_1 = _answer(answers, "q1_1")
    q1_2 = _answer(answers, "q1_2")
    q1_3 = _answer(answers, "q1_3")

    if q1_2 in NO:
        return "high"
    if q1_2 == "NI" and q1_3 in YES:
        return "high"
    if q1_2 in YES and q1_3 in NO_OR_NI and q1_1 in YES_OR_NI:
        return "low"
    if q1_2 in YES and q1_3 in YES:
        return "some_concerns"
    if q1_2 == "NI" and q1_3 in NO_OR_NI:
        return "some_concerns"
    if q1_1 == "NI" and q1_2 == "NI" and q1_3 == "NI":
        return "some_concerns"
    return "some_concerns"


def _risk_d2_assignment(answers: Mapping[str, AnswerOption]) -> DomainRisk:
    q2_6 = _answer(answers, "q2a_6")
    q2_7 = _answer(answers, "q2a_7")

    if q2_6 in YES:
        return "low"
    if q2_6 in NO_OR_NI:
        if q2_7 in NO:
            return "some_concerns"
        if q2_7 in YES_OR_NI:
            return "high"
    return "some_concerns"


def _risk_d2_adherence(answers: Mapping[str, AnswerOption]) -> DomainRisk:
    q2_1 = _answer(answers, "q2b_1")
    q2_2 = _answer(answers, "q2b_2")
    q2_3 = _answer(answers, "q2b_3")
    q2_4 = _answer(answers, "q2b_4")
    q2_5 = _answer(answers, "q2b_5")
    q2_6 = _answer(answers, "q2b_6")

    awareness_low = q2_1 in NO and q2_2 in NO
    awareness_high = q2_1 in YES_OR_NI or q2_2 in YES_OR_NI

    q2_3_ok = q2_3 in (YES | NA)
    q2_3_bad = q2_3 in (NO | NO_INFO)

    q2_4_low = q2_4 in NO_OR_NA
    q2_5_low = q2_5 in NO_OR_NA
    q2_4_high = q2_4 in YES_OR_NI
    q2_5_high = q2_5 in YES_OR_NI

    if awareness_low and q2_4_low and q2_5_low:
        return "low"
    if awareness_high and q2_3_ok and q2_4_low and q2_5_low:
        return "low"

    if awareness_low and (q2_4_high or q2_5_high) and q2_6 in YES:
        return "some_concerns"
    if awareness_high and q2_3_ok and (q2_4_high or q2_5_high) and q2_6 in YES:
        return "some_concerns"
    if awareness_high and q2_3_bad and q2_6 in YES:
        return "some_concerns"

    if awareness_low and (q2_4_high or q2_5_high) and q2_6 in NO_OR_NI:
        return "high"
    if awareness_high and q2_3_ok and (q2_4_high or q2_5_high) and q2_6 in NO_OR_NI:
        return "high"
    if awareness_high and q2_3_bad and q2_6 in NO_OR_NI:
        return "high"

    return "some_concerns"


def _risk_d3(answers: Mapping[str, AnswerOption]) -> DomainRisk:
    q3_1 = _answer(answers, "q3_1")
    q3_2 = _answer(answers, "q3_2")
    q3_3 = _answer(answers, "q3_3")
    q3_4 = _answer(answers, "q3_4")

    if q3_1 in YES:
        return "low"
    if q3_1 not in YES and q3_2 in YES:
        return "low"
    if q3_1 not in YES and q3_2 not in YES and q3_3 in NO:
        return "low"
    if q3_1 not in YES and q3_2 not in YES and q3_3 in YES_OR_NI and q3_4 in NO:
        return "some_concerns"
    if (
        q3_1 not in YES
        and q3_2 not in YES
        and q3_3 in YES_OR_NI
        and q3_4 in YES_OR_NI
    ):
        return "high"
    return "some_concerns"


def _risk_d4(answers: Mapping[str, AnswerOption]) -> DomainRisk:
    q4_1 = _answer(answers, "q4_1")
    q4_2 = _answer(answers, "q4_2")
    q4_3 = _answer(answers, "q4_3")
    q4_4 = _answer(answers, "q4_4")
    q4_5 = _answer(answers, "q4_5")

    if q4_1 in YES:
        return "high"
    if q4_2 in YES:
        return "high"
    if q4_2 == "NI":
        return "some_concerns"
    if q4_2 in NO:
        if q4_3 in NO:
            return "low"
        if q4_3 in YES_OR_NI:
            if q4_4 in NO:
                return "low"
            if q4_4 in YES_OR_NI:
                if q4_5 in NO:
                    return "some_concerns"
                if q4_5 in YES_OR_NI:
                    return "high"
    return "some_concerns"


def _risk_d5(answers: Mapping[str, AnswerOption]) -> DomainRisk:
    q5_1 = _answer(answers, "q5_1")
    q5_2 = _answer(answers, "q5_2")
    q5_3 = _answer(answers, "q5_3")

    if q5_2 in YES:
        return "high"
    if q5_3 in YES:
        return "high"
    if q5_1 in YES and q5_2 in NO and q5_3 in NO:
        return "low"
    if q5_1 in NO_OR_NI and q5_2 in NO and q5_3 in NO:
        return "some_concerns"
    if q5_2 == "NI" or q5_3 == "NI":
        return "some_concerns"
    return "some_concerns"


__all__ = ["evaluate_domain_risk"]
