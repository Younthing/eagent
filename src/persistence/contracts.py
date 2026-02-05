"""Persistence protocol contracts."""

from __future__ import annotations

from typing import Any, Protocol

from persistence.models import (
    ArtifactRecord,
    BatchRecord,
    CacheEntry,
    DocumentRecord,
    RunRecord,
    RunSummaryRecord,
)


class RunStore(Protocol):
    def create_document(
        self, *, sha256: str, filename: str | None, bytes_size: int | None
    ) -> DocumentRecord: ...

    def create_batch(
        self, *, name: str | None, metadata: dict[str, Any] | None
    ) -> BatchRecord: ...

    def create_run(self, record: RunRecord) -> None: ...

    def update_run(self, run_id: str, **fields: object) -> None: ...

    def insert_run_summary(self, summary: RunSummaryRecord) -> None: ...

    def list_run_summaries(self, *, batch_id: str | None = None) -> list[dict[str, Any]]: ...


class ArtifactStore(Protocol):
    def write_text(self, content: str, *, ext: str) -> ArtifactRecord: ...

    def write_bytes(self, content: bytes, *, ext: str) -> ArtifactRecord: ...

    def write_json(self, payload: object, *, ext: str = "json") -> ArtifactRecord: ...


class CacheStore(Protocol):
    def get_entry(self, *, stage: str, cache_key: str) -> CacheEntry | None: ...

    def put_entry(self, entry: CacheEntry) -> None: ...

    def touch_entry(self, *, stage: str, cache_key: str) -> None: ...

    def delete_entry(self, *, stage: str, cache_key: str) -> None: ...

    def list_cache_stats(self) -> list[dict[str, Any]]: ...


__all__ = ["ArtifactStore", "CacheStore", "RunStore"]
