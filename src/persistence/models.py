"""Lightweight persistence records."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class DocumentRecord:
    doc_id: str
    sha256: str
    filename: str | None
    bytes: int | None
    created_at: datetime


@dataclass(frozen=True)
class BatchRecord:
    batch_id: str
    name: str | None
    metadata: dict[str, Any] | None
    created_at: datetime


@dataclass(frozen=True)
class RunRecord:
    run_id: str
    doc_id: str | None
    batch_id: str | None
    status: str
    created_at: datetime
    completed_at: datetime | None
    options_json: str | None
    options_hash: str | None
    code_version: str | None
    question_set_version: str | None
    runtime_ms: int | None
    warnings_json: str | None


@dataclass(frozen=True)
class ArtifactRecord:
    artifact_id: str
    content_hash: str
    type: str
    path: str
    bytes: int
    created_at: datetime


@dataclass(frozen=True)
class RunSummaryRecord:
    run_id: str
    overall_risk: str | None
    domain_risks_json: str | None
    citations_count: int | None
    validated_evidence_count: int | None


@dataclass(frozen=True)
class CacheEntry:
    cache_key: str
    stage: str
    content_hash: str
    path: str
    created_at: datetime
    last_accessed: datetime | None


__all__ = [
    "ArtifactRecord",
    "BatchRecord",
    "CacheEntry",
    "DocumentRecord",
    "RunRecord",
    "RunSummaryRecord",
]
