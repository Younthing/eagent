"""Routing helpers for ROB2 graph workflows.

Milestone 7 requires validation failures to trigger an automatic rollback to
the evidence location layer. LangGraph implements this via conditional edges
that route based on state.
"""

from __future__ import annotations

from typing import Any, Literal, Mapping


def _as_int(value: object, default: int) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except Exception:
        return default


def _truthy(value: object, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def validation_should_retry(state: Mapping[str, Any]) -> Literal["retry", "end"]:
    """Route after Milestone 7 validation to either retry evidence location or end."""
    attempt = _as_int(state.get("validation_attempt"), 0)
    max_retries = _as_int(state.get("validation_max_retries"), 0)

    completeness_passed = bool(state.get("completeness_passed"))
    fail_on_consistency = _truthy(state.get("validation_fail_on_consistency"), True)
    consistency_failed = state.get("consistency_failed_questions") or []
    consistency_has_failures = isinstance(consistency_failed, list) and bool(consistency_failed)

    passed = completeness_passed and (not fail_on_consistency or not consistency_has_failures)
    if passed:
        return "end"
    if attempt >= max_retries:
        return "end"
    return "retry"


__all__ = ["validation_should_retry"]

