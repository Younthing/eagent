"""External response schemas for ROB2 runs."""

from __future__ import annotations

from typing import Any, List

from pydantic import BaseModel, ConfigDict, Field

from schemas.internal.results import Rob2FinalOutput


class Rob2RunResult(BaseModel):
    run_id: str | None = None
    result: Rob2FinalOutput
    table_markdown: str
    reports: dict[str, Any] | None = None
    audit_reports: list[dict] | None = None
    debug: dict[str, Any] | None = None
    runtime_ms: int | None = None
    warnings: List[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


__all__ = ["Rob2RunResult"]
