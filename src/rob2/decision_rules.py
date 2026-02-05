"""Rule-based ROB2 domain risk decision trees."""

from __future__ import annotations

from typing import Mapping, Optional, Literal

from schemas.internal.decisions import AnswerOption, DomainRisk
from schemas.internal.locator import DomainId

EffectType = Literal["assignment", "adherence"]
RuleTrace = list[str]

YES = {"Y", "PY"}
NO = {"N", "PN"}
NO_INFO = {"NI"}
NA = {"NA"}
YES_OR_NI = YES | NO_INFO
NO_OR_NI = NO | NO_INFO
YES_OR_NI_OR_NA = YES_OR_NI | NA
NO_OR_NA = NO | NA


def evaluate_domain_risk_with_trace(
    domain: DomainId,
    answers: Mapping[str, AnswerOption],
    *,
    effect_type: Optional[EffectType] = None,
) -> tuple[Optional[DomainRisk], RuleTrace]:
    """Return rule-based domain risk with trace, or (None, trace) if unavailable."""
    if domain == "D1":
        return _risk_d1(answers)
    if domain == "D2":
        if effect_type == "assignment":
            return _risk_d2_assignment(answers)
        if effect_type == "adherence":
            return _risk_d2_adherence(answers)
        return None, ["D2:R0 missing effect_type -> no rule risk"]
    if domain == "D3":
        return _risk_d3(answers)
    if domain == "D4":
        return _risk_d4(answers)
    if domain == "D5":
        return _risk_d5(answers)
    return None, [f"{domain}:R0 unknown domain -> no rule risk"]




def _answer(answers: Mapping[str, AnswerOption], question_id: str) -> AnswerOption:
    return answers.get(question_id, "NI")


def _risk_d1(answers: Mapping[str, AnswerOption]) -> tuple[DomainRisk, RuleTrace]:
    q1_1 = _answer(answers, "q1_1")
    q1_2 = _answer(answers, "q1_2")
    q1_3 = _answer(answers, "q1_3")

    if q1_2 in NO:
        return "high", ["D1:R1 q1_2 in NO -> high"]
    if q1_2 == "NI" and q1_3 in YES:
        return "high", ["D1:R2 q1_2=NI & q1_3 in YES -> high"]
    if q1_2 in YES and q1_3 in NO_OR_NI and q1_1 in YES_OR_NI:
        return "low", ["D1:R3 q1_2 in YES & q1_3 in NO/NI & q1_1 in YES/NI -> low"]
    if q1_2 in YES and q1_3 in YES:
        return "some_concerns", ["D1:R4 q1_2 in YES & q1_3 in YES -> some_concerns"]
    if q1_2 == "NI" and q1_3 in NO_OR_NI:
        return "some_concerns", ["D1:R5 q1_2=NI & q1_3 in NO/NI -> some_concerns"]
    if q1_1 == "NI" and q1_2 == "NI" and q1_3 == "NI":
        return "some_concerns", ["D1:R6 q1_1=q1_2=q1_3=NI -> some_concerns"]
    return "some_concerns", ["D1:R0 default -> some_concerns"]


def _risk_d2_assignment(answers: Mapping[str, AnswerOption]) -> tuple[DomainRisk, RuleTrace]:
    q2_6 = _answer(answers, "q2a_6")
    q2_7 = _answer(answers, "q2a_7")

    if q2_6 in YES:
        return "low", ["D2A:R1 q2a_6 in YES -> low"]
    if q2_6 in NO_OR_NI:
        if q2_7 in NO:
            return "some_concerns", ["D2A:R2 q2a_6 in NO/NI & q2a_7 in NO -> some_concerns"]
        if q2_7 in YES_OR_NI:
            return "high", ["D2A:R3 q2a_6 in NO/NI & q2a_7 in YES/NI -> high"]
    return "some_concerns", ["D2A:R0 default -> some_concerns"]


def _risk_d2_adherence(answers: Mapping[str, AnswerOption]) -> tuple[DomainRisk, RuleTrace]:
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
        return "low", ["D2B:R1 awareness_low & q2b_4/5 low -> low"]
    if awareness_high and q2_3_ok and q2_4_low and q2_5_low:
        return "low", ["D2B:R2 awareness_high & q2b_3 ok & q2b_4/5 low -> low"]

    if awareness_low and (q2_4_high or q2_5_high) and q2_6 in YES:
        return "some_concerns", ["D2B:R3 awareness_low & q2b_4/5 high & q2b_6 YES -> some_concerns"]
    if awareness_high and q2_3_ok and (q2_4_high or q2_5_high) and q2_6 in YES:
        return "some_concerns", ["D2B:R4 awareness_high & q2b_3 ok & q2b_4/5 high & q2b_6 YES -> some_concerns"]
    if awareness_high and q2_3_bad and q2_6 in YES:
        return "some_concerns", ["D2B:R5 awareness_high & q2b_3 bad & q2b_6 YES -> some_concerns"]

    if awareness_low and (q2_4_high or q2_5_high) and q2_6 in NO_OR_NI:
        return "high", ["D2B:R6 awareness_low & q2b_4/5 high & q2b_6 NO/NI -> high"]
    if awareness_high and q2_3_ok and (q2_4_high or q2_5_high) and q2_6 in NO_OR_NI:
        return "high", ["D2B:R7 awareness_high & q2b_3 ok & q2b_4/5 high & q2b_6 NO/NI -> high"]
    if awareness_high and q2_3_bad and q2_6 in NO_OR_NI:
        return "high", ["D2B:R8 awareness_high & q2b_3 bad & q2b_6 NO/NI -> high"]

    return "some_concerns", ["D2B:R0 default -> some_concerns"]


def _risk_d3(answers: Mapping[str, AnswerOption]) -> tuple[DomainRisk, RuleTrace]:
    q3_1 = _answer(answers, "q3_1")
    q3_2 = _answer(answers, "q3_2")
    q3_3 = _answer(answers, "q3_3")
    q3_4 = _answer(answers, "q3_4")

    if q3_1 in YES:
        return "low", ["D3:R1 q3_1 in YES -> low"]
    if q3_1 not in YES and q3_2 in YES:
        return "low", ["D3:R2 q3_1 not YES & q3_2 in YES -> low"]
    if q3_1 not in YES and q3_2 not in YES and q3_3 in NO:
        return "low", ["D3:R3 q3_1 not YES & q3_2 not YES & q3_3 in NO -> low"]
    if q3_1 not in YES and q3_2 not in YES and q3_3 in YES_OR_NI and q3_4 in NO:
        return "some_concerns", ["D3:R4 q3_1 not YES & q3_2 not YES & q3_3 in YES/NI & q3_4 in NO -> some_concerns"]
    if (
        q3_1 not in YES
        and q3_2 not in YES
        and q3_3 in YES_OR_NI
        and q3_4 in YES_OR_NI
    ):
        return "high", ["D3:R5 q3_1 not YES & q3_2 not YES & q3_3 in YES/NI & q3_4 in YES/NI -> high"]
    return "some_concerns", ["D3:R0 default -> some_concerns"]


def _risk_d4(answers: Mapping[str, AnswerOption]) -> tuple[DomainRisk, RuleTrace]:
    q4_1 = _answer(answers, "q4_1")
    q4_2 = _answer(answers, "q4_2")
    q4_3 = _answer(answers, "q4_3")
    q4_4 = _answer(answers, "q4_4")
    q4_5 = _answer(answers, "q4_5")

    if q4_1 in YES:
        return "high", ["D4:R1 q4_1 in YES -> high"]
    if q4_2 in YES:
        return "high", ["D4:R2 q4_2 in YES -> high"]
    if q4_2 == "NI":
        return "some_concerns", ["D4:R3 q4_2=NI -> some_concerns"]
    if q4_2 in NO:
        if q4_3 in NO:
            return "low", ["D4:R4 q4_2 in NO & q4_3 in NO -> low"]
        if q4_3 in YES_OR_NI:
            if q4_4 in NO:
                return "low", ["D4:R5 q4_2 in NO & q4_3 in YES/NI & q4_4 in NO -> low"]
            if q4_4 in YES_OR_NI:
                if q4_5 in NO:
                    return "some_concerns", ["D4:R6 q4_2 in NO & q4_3 in YES/NI & q4_4 in YES/NI & q4_5 in NO -> some_concerns"]
                if q4_5 in YES_OR_NI:
                    return "high", ["D4:R7 q4_2 in NO & q4_3 in YES/NI & q4_4 in YES/NI & q4_5 in YES/NI -> high"]
    return "some_concerns", ["D4:R0 default -> some_concerns"]


def _risk_d5(answers: Mapping[str, AnswerOption]) -> tuple[DomainRisk, RuleTrace]:
    q5_1 = _answer(answers, "q5_1")
    q5_2 = _answer(answers, "q5_2")
    q5_3 = _answer(answers, "q5_3")

    if q5_2 in YES:
        return "high", ["D5:R1 q5_2 in YES -> high"]
    if q5_3 in YES:
        return "high", ["D5:R2 q5_3 in YES -> high"]
    if q5_1 in YES and q5_2 in NO and q5_3 in NO:
        return "low", ["D5:R3 q5_1 in YES & q5_2 in NO & q5_3 in NO -> low"]
    if q5_1 in NO_OR_NI and q5_2 in NO and q5_3 in NO:
        return "some_concerns", ["D5:R4 q5_1 in NO/NI & q5_2 in NO & q5_3 in NO -> some_concerns"]
    if q5_2 == "NI" or q5_3 == "NI":
        return "some_concerns", ["D5:R5 q5_2 or q5_3 is NI -> some_concerns"]
    return "some_concerns", ["D5:R0 default -> some_concerns"]


__all__ = ["evaluate_domain_risk_with_trace"]
