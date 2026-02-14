from __future__ import annotations

from rob2.decision_rules import evaluate_domain_risk_with_trace
from schemas.internal.decisions import AnswerOption


def test_d1_rules() -> None:
    answers_high: dict[str, AnswerOption] = {"q1_2": "N", "q1_1": "Y", "q1_3": "N"}
    answers_low: dict[str, AnswerOption] = {"q1_1": "Y", "q1_2": "Y", "q1_3": "N"}
    answers_high_ni: dict[str, AnswerOption] = {
        "q1_1": "NI",
        "q1_2": "NI",
        "q1_3": "Y",
    }
    assert evaluate_domain_risk_with_trace("D1", answers_high)[0] == "high"
    assert evaluate_domain_risk_with_trace("D1", answers_low)[0] == "low"
    assert evaluate_domain_risk_with_trace("D1", answers_high_ni)[0] == "high"


def test_rule_trace_includes_rule_id() -> None:
    answers: dict[str, AnswerOption] = {"q1_2": "N", "q1_1": "Y", "q1_3": "N"}
    risk, trace = evaluate_domain_risk_with_trace("D1", answers)
    assert risk == "high"
    assert trace and trace[0].startswith("D1:R1")


def test_d2_assignment_rules() -> None:
    low_answers: dict[str, AnswerOption] = {
        "q2a_1": "N",
        "q2a_2": "N",
        "q2a_6": "Y",
        "q2a_7": "NA",
    }
    some_answers: dict[str, AnswerOption] = {
        "q2a_1": "N",
        "q2a_2": "N",
        "q2a_6": "N",
        "q2a_7": "N",
    }
    high_answers: dict[str, AnswerOption] = {
        "q2a_1": "Y",
        "q2a_2": "N",
        "q2a_3": "Y",
        "q2a_4": "Y",
        "q2a_5": "N",
        "q2a_6": "Y",
        "q2a_7": "NA",
    }
    adherence_answers: dict[str, AnswerOption] = {"q2b_6": "Y"}
    assert (
        evaluate_domain_risk_with_trace("D2", low_answers, effect_type="assignment")[0]
        == "low"
    )
    assert (
        evaluate_domain_risk_with_trace("D2", some_answers, effect_type="assignment")[0]
        == "some_concerns"
    )
    assert (
        evaluate_domain_risk_with_trace("D2", high_answers, effect_type="assignment")[0]
        == "high"
    )
    assert (
        evaluate_domain_risk_with_trace("D2", adherence_answers, effect_type="adherence")[0]
        == "some_concerns"
    )


def test_d2_adherence_rules() -> None:
    low_answers: dict[str, AnswerOption] = {
        "q2b_1": "N",
        "q2b_2": "N",
        "q2b_4": "N",
        "q2b_5": "PN",
    }
    low_answers_alt: dict[str, AnswerOption] = {
        "q2b_1": "Y",
        "q2b_2": "N",
        "q2b_3": "PY",
        "q2b_4": "N",
        "q2b_5": "NA",
    }
    some_answers: dict[str, AnswerOption] = {
        "q2b_1": "N",
        "q2b_2": "N",
        "q2b_4": "Y",
        "q2b_5": "N",
        "q2b_6": "Y",
    }
    high_answers: dict[str, AnswerOption] = {
        "q2b_1": "Y",
        "q2b_2": "N",
        "q2b_3": "NI",
        "q2b_6": "N",
    }
    assert (
        evaluate_domain_risk_with_trace("D2", low_answers, effect_type="adherence")[0]
        == "low"
    )
    assert (
        evaluate_domain_risk_with_trace("D2", low_answers_alt, effect_type="adherence")[0]
        == "low"
    )
    assert (
        evaluate_domain_risk_with_trace("D2", some_answers, effect_type="adherence")[0]
        == "some_concerns"
    )
    assert (
        evaluate_domain_risk_with_trace("D2", high_answers, effect_type="adherence")[0]
        == "high"
    )


def test_d3_rules() -> None:
    low_answers: dict[str, AnswerOption] = {"q3_1": "Y"}
    some_answers: dict[str, AnswerOption] = {
        "q3_1": "N",
        "q3_2": "N",
        "q3_3": "Y",
        "q3_4": "N",
    }
    high_answers: dict[str, AnswerOption] = {
        "q3_1": "N",
        "q3_2": "N",
        "q3_3": "Y",
        "q3_4": "Y",
    }
    assert evaluate_domain_risk_with_trace("D3", low_answers)[0] == "low"
    assert evaluate_domain_risk_with_trace("D3", some_answers)[0] == "some_concerns"
    assert evaluate_domain_risk_with_trace("D3", high_answers)[0] == "high"


def test_d4_rules() -> None:
    high_answers: dict[str, AnswerOption] = {"q4_1": "Y"}
    some_answers: dict[str, AnswerOption] = {"q4_1": "N", "q4_2": "NI"}
    low_answers: dict[str, AnswerOption] = {"q4_1": "N", "q4_2": "N", "q4_3": "N"}
    high_answers_2: dict[str, AnswerOption] = {
        "q4_1": "N",
        "q4_2": "N",
        "q4_3": "Y",
        "q4_4": "Y",
        "q4_5": "Y",
    }
    assert evaluate_domain_risk_with_trace("D4", high_answers)[0] == "high"
    assert evaluate_domain_risk_with_trace("D4", some_answers)[0] == "some_concerns"
    assert evaluate_domain_risk_with_trace("D4", low_answers)[0] == "low"
    assert evaluate_domain_risk_with_trace("D4", high_answers_2)[0] == "high"


def test_d5_rules() -> None:
    high_answers: dict[str, AnswerOption] = {"q5_2": "Y"}
    low_answers: dict[str, AnswerOption] = {"q5_1": "Y", "q5_2": "N", "q5_3": "N"}
    some_answers: dict[str, AnswerOption] = {
        "q5_1": "N",
        "q5_2": "N",
        "q5_3": "N",
    }
    ni_answers: dict[str, AnswerOption] = {"q5_2": "NI", "q5_3": "N"}
    assert evaluate_domain_risk_with_trace("D5", high_answers)[0] == "high"
    assert evaluate_domain_risk_with_trace("D5", low_answers)[0] == "low"
    assert evaluate_domain_risk_with_trace("D5", some_answers)[0] == "some_concerns"
    assert evaluate_domain_risk_with_trace("D5", ni_answers)[0] == "some_concerns"
