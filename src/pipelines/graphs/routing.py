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


def validation_should_retry(
    state: Mapping[str, Any],
) -> Literal["retry", "proceed", "fallback"]:
    """Route after Milestone 7 validation to retry, fallback, or proceed."""
    attempt = _as_int(state.get("validation_attempt"), 0)
    max_retries = _as_int(state.get("validation_max_retries"), 0)

    completeness_passed = bool(state.get("completeness_passed"))
    fail_on_consistency = _truthy(state.get("validation_fail_on_consistency"), True)
    consistency_failed = state.get("consistency_failed_questions") or []
    consistency_has_failures = isinstance(consistency_failed, list) and bool(
        consistency_failed
    )

    passed = completeness_passed and (
        not fail_on_consistency or not consistency_has_failures
    )
    if passed:
        return "proceed"
    if attempt >= max_retries:
        return "fallback"
    return "retry"


def domain_audit_should_run(state: Mapping[str, Any]) -> Literal["audit", "skip"]:
    """Route after each domain agent to run the per-domain audit or skip."""
    mode = str(state.get("domain_audit_mode") or "none").strip().lower()
    if mode in {"0", "false", "off"}:
        mode = "none"
    return "audit" if mode != "none" else "skip"


def domain_audit_should_run_final(state: Mapping[str, Any]) -> Literal["final", "skip"]:
    """Route after per-domain audits to optionally run a final all-domain audit."""
    mode = str(state.get("domain_audit_mode") or "none").strip().lower()
    if mode in {"0", "false", "off"}:
        mode = "none"
    if mode == "none":
        return "skip"
    enabled = _truthy(state.get("domain_audit_final"), False)
    return "final" if enabled else "skip"


__all__ = [
    "domain_audit_should_run",
    "domain_audit_should_run_final",
    "validation_should_retry",
]
