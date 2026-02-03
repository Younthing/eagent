from __future__ import annotations

from pipelines.graphs.routing import validation_should_retry


def test_validation_should_retry_routes_to_end_when_passed() -> None:
    assert (
        validation_should_retry(
            {
                "validation_attempt": 0,
                "validation_max_retries": 3,
                "completeness_passed": True,
                "consistency_failed_questions": [],
                "validation_fail_on_consistency": True,
            }
        )
        == "proceed"
    )


def test_validation_should_retry_routes_to_retry_when_failed_and_budget_left() -> None:
    assert (
        validation_should_retry(
            {
                "validation_attempt": 0,
                "validation_max_retries": 2,
                "completeness_passed": False,
                "consistency_failed_questions": [],
                "validation_fail_on_consistency": True,
            }
        )
        == "retry"
    )


def test_validation_should_retry_routes_to_fallback_when_failed_and_budget_exhausted() -> None:
    assert (
        validation_should_retry(
            {
                "validation_attempt": 2,
                "validation_max_retries": 2,
                "completeness_passed": False,
                "consistency_failed_questions": [],
                "validation_fail_on_consistency": True,
            }
        )
        == "fallback"
    )


def test_validation_should_retry_treats_consistency_fail_as_failure_when_enabled() -> None:
    assert (
        validation_should_retry(
            {
                "validation_attempt": 0,
                "validation_max_retries": 1,
                "completeness_passed": True,
                "consistency_failed_questions": ["q1_1"],
                "validation_fail_on_consistency": True,
            }
        )
        == "retry"
    )


def test_validation_should_retry_ignores_consistency_fail_when_disabled() -> None:
    assert (
        validation_should_retry(
            {
                "validation_attempt": 0,
                "validation_max_retries": 1,
                "completeness_passed": True,
                "consistency_failed_questions": ["q1_1"],
                "validation_fail_on_consistency": False,
            }
        )
        == "proceed"
    )
