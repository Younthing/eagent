from __future__ import annotations

from rob2.decision_rules import evaluate_domain_risk
from schemas.internal.decisions import AnswerOption


def test_d1_rules() -> None:
    answers_high: dict[str, AnswerOption] = {"q1_2": "N", "q1_1": "Y", "q1_3": "N"}
    answers_low: dict[str, AnswerOption] = {"q1_1": "Y", "q1_2": "Y", "q1_3": "N"}
    answers_high_ni: dict[str, AnswerOption] = {
        "q1_1": "NI",
        "q1_2": "NI",
        "q1_3": "Y",
    }
    assert evaluate_domain_risk("D1", answers_high) == "high"
    assert evaluate_domain_risk("D1", answers_low) == "low"
    assert evaluate_domain_risk("D1", answers_high_ni) == "high"


def test_d2_assignment_rules() -> None:
    low_answers: dict[str, AnswerOption] = {"q2a_6": "Y", "q2a_7": "NA"}
    some_answers: dict[str, AnswerOption] = {"q2a_6": "N", "q2a_7": "N"}
    high_answers: dict[str, AnswerOption] = {"q2a_6": "N", "q2a_7": "NI"}
    adherence_answers: dict[str, AnswerOption] = {"q2b_6": "Y"}
    assert (
        evaluate_domain_risk("D2", low_answers, effect_type="assignment") == "low"
    )
    assert (
        evaluate_domain_risk("D2", some_answers, effect_type="assignment")
        == "some_concerns"
    )
    assert (
        evaluate_domain_risk("D2", high_answers, effect_type="assignment") == "high"
    )
    assert (
        evaluate_domain_risk("D2", adherence_answers, effect_type="adherence")
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
        evaluate_domain_risk("D2", low_answers, effect_type="adherence") == "low"
    )
    assert (
        evaluate_domain_risk("D2", low_answers_alt, effect_type="adherence") == "low"
    )
    assert (
        evaluate_domain_risk("D2", some_answers, effect_type="adherence")
        == "some_concerns"
    )
    assert (
        evaluate_domain_risk("D2", high_answers, effect_type="adherence") == "high"
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
    assert evaluate_domain_risk("D3", low_answers) == "low"
    assert evaluate_domain_risk("D3", some_answers) == "some_concerns"
    assert evaluate_domain_risk("D3", high_answers) == "high"


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
    assert evaluate_domain_risk("D4", high_answers) == "high"
    assert evaluate_domain_risk("D4", some_answers) == "some_concerns"
    assert evaluate_domain_risk("D4", low_answers) == "low"
    assert evaluate_domain_risk("D4", high_answers_2) == "high"


def test_d5_rules() -> None:
    high_answers: dict[str, AnswerOption] = {"q5_2": "Y"}
    low_answers: dict[str, AnswerOption] = {"q5_1": "Y", "q5_2": "N", "q5_3": "N"}
    some_answers: dict[str, AnswerOption] = {
        "q5_1": "N",
        "q5_2": "N",
        "q5_3": "N",
    }
    ni_answers: dict[str, AnswerOption] = {"q5_2": "NI", "q5_3": "N"}
    assert evaluate_domain_risk("D5", high_answers) == "high"
    assert evaluate_domain_risk("D5", low_answers) == "low"
    assert evaluate_domain_risk("D5", some_answers) == "some_concerns"
    assert evaluate_domain_risk("D5", ni_answers) == "some_concerns"
