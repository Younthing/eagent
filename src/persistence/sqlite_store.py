"""SQLite-backed metadata store for persistence and cache."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from persistence.models import (
    ArtifactRecord,
    BatchRecord,
    CacheEntry,
    DocumentRecord,
    RunRecord,
    RunSummaryRecord,
)


_SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS documents (
    doc_id TEXT PRIMARY KEY,
    sha256 TEXT NOT NULL,
    filename TEXT,
    bytes INTEGER,
    created_at TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_documents_sha256 ON documents(sha256);

CREATE TABLE IF NOT EXISTS batches (
    batch_id TEXT PRIMARY KEY,
    name TEXT,
    metadata_json TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    doc_id TEXT,
    batch_id TEXT,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    completed_at TEXT,
    options_json TEXT,
    options_hash TEXT,
    code_version TEXT,
    question_set_version TEXT,
    runtime_ms INTEGER,
    warnings_json TEXT,
    FOREIGN KEY(doc_id) REFERENCES documents(doc_id),
    FOREIGN KEY(batch_id) REFERENCES batches(batch_id)
);
CREATE INDEX IF NOT EXISTS idx_runs_batch_id ON runs(batch_id);
CREATE INDEX IF NOT EXISTS idx_runs_doc_id ON runs(doc_id);

CREATE TABLE IF NOT EXISTS run_summary (
    run_id TEXT PRIMARY KEY,
    overall_risk TEXT,
    domain_risks_json TEXT,
    citations_count INTEGER,
    validated_evidence_count INTEGER,
    FOREIGN KEY(run_id) REFERENCES runs(run_id)
);

CREATE TABLE IF NOT EXISTS artifacts (
    artifact_id TEXT PRIMARY KEY,
    content_hash TEXT NOT NULL,
    type TEXT NOT NULL,
    path TEXT NOT NULL,
    bytes INTEGER NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_artifacts_hash ON artifacts(content_hash);

CREATE TABLE IF NOT EXISTS run_artifacts (
    run_id TEXT NOT NULL,
    artifact_id TEXT NOT NULL,
    type TEXT NOT NULL,
    FOREIGN KEY(run_id) REFERENCES runs(run_id),
    FOREIGN KEY(artifact_id) REFERENCES artifacts(artifact_id)
);
CREATE INDEX IF NOT EXISTS idx_run_artifacts_run_id ON run_artifacts(run_id);

CREATE TABLE IF NOT EXISTS cache_entries (
    cache_key TEXT NOT NULL,
    stage TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    path TEXT NOT NULL,
    created_at TEXT NOT NULL,
    last_accessed TEXT,
    PRIMARY KEY(stage, cache_key)
);
CREATE INDEX IF NOT EXISTS idx_cache_entries_stage ON cache_entries(stage);
"""


class SqliteStore:
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @property
    def path(self) -> Path:
        return self._path

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path)
        conn.row_factory = sqlite3.Row
        return conn

    def _initialize(self) -> None:
        with self._connect() as conn:
            conn.executescript(_SCHEMA)
            conn.commit()

    def create_document(
        self,
        *,
        sha256: str,
        filename: str | None,
        bytes_size: int | None,
    ) -> DocumentRecord:
        existing = self._fetch_one(
            "SELECT * FROM documents WHERE sha256 = ?", (sha256,)
        )
        if existing:
            return _row_to_document(existing)
        doc_id = _new_id("doc")
        created_at = _now_iso()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO documents (doc_id, sha256, filename, bytes, created_at) VALUES (?, ?, ?, ?, ?)",
                (doc_id, sha256, filename, bytes_size, created_at),
            )
            conn.commit()
        return DocumentRecord(
            doc_id=doc_id,
            sha256=sha256,
            filename=filename,
            bytes=bytes_size,
            created_at=_from_iso(created_at),
        )

    def create_batch(
        self,
        *,
        name: str | None,
        metadata: dict[str, Any] | None,
    ) -> BatchRecord:
        batch_id = _new_id("batch")
        created_at = _now_iso()
        metadata_json = json.dumps(metadata, ensure_ascii=False, sort_keys=True) if metadata else None
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO batches (batch_id, name, metadata_json, created_at) VALUES (?, ?, ?, ?)",
                (batch_id, name, metadata_json, created_at),
            )
            conn.commit()
        return BatchRecord(
            batch_id=batch_id,
            name=name,
            metadata=metadata,
            created_at=_from_iso(created_at),
        )

    def create_run(self, record: RunRecord) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO runs (
                    run_id, doc_id, batch_id, status, created_at, completed_at,
                    options_json, options_hash, code_version, question_set_version,
                    runtime_ms, warnings_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.run_id,
                    record.doc_id,
                    record.batch_id,
                    record.status,
                    record.created_at.isoformat(),
                    record.completed_at.isoformat() if record.completed_at else None,
                    record.options_json,
                    record.options_hash,
                    record.code_version,
                    record.question_set_version,
                    record.runtime_ms,
                    record.warnings_json,
                ),
            )
            conn.commit()

    def update_run(self, run_id: str, **fields: object) -> None:
        if not fields:
            return
        columns = []
        values: list[object] = []
        for key, value in fields.items():
            columns.append(f"{key} = ?")
            if isinstance(value, datetime):
                values.append(value.isoformat())
            else:
                values.append(value)
        values.append(run_id)
        with self._connect() as conn:
            conn.execute(
                f"UPDATE runs SET {', '.join(columns)} WHERE run_id = ?",
                values,
            )
            conn.commit()

    def insert_run_summary(self, summary: RunSummaryRecord) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO run_summary (
                    run_id, overall_risk, domain_risks_json, citations_count, validated_evidence_count
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    summary.run_id,
                    summary.overall_risk,
                    summary.domain_risks_json,
                    summary.citations_count,
                    summary.validated_evidence_count,
                ),
            )
            conn.commit()

    def insert_artifact(self, record: ArtifactRecord) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO artifacts (
                    artifact_id, content_hash, type, path, bytes, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    record.artifact_id,
                    record.content_hash,
                    record.type,
                    record.path,
                    record.bytes,
                    record.created_at.isoformat(),
                ),
            )
            conn.commit()

    def link_artifact(self, *, run_id: str, artifact_id: str, artifact_type: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO run_artifacts (run_id, artifact_id, type) VALUES (?, ?, ?)",
                (run_id, artifact_id, artifact_type),
            )
            conn.commit()

    def get_cache_entry(self, *, stage: str, cache_key: str) -> CacheEntry | None:
        row = self._fetch_one(
            "SELECT * FROM cache_entries WHERE stage = ? AND cache_key = ?",
            (stage, cache_key),
        )
        return _row_to_cache(row) if row else None

    def put_cache_entry(self, entry: CacheEntry) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO cache_entries (
                    cache_key, stage, content_hash, path, created_at, last_accessed
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.cache_key,
                    entry.stage,
                    entry.content_hash,
                    entry.path,
                    entry.created_at.isoformat(),
                    entry.last_accessed.isoformat() if entry.last_accessed else None,
                ),
            )
            conn.commit()

    def touch_cache_entry(self, *, stage: str, cache_key: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE cache_entries SET last_accessed = ? WHERE stage = ? AND cache_key = ?",
                (_now_iso(), stage, cache_key),
            )
            conn.commit()

    def delete_cache_entry(self, *, stage: str, cache_key: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM cache_entries WHERE stage = ? AND cache_key = ?",
                (stage, cache_key),
            )
            conn.commit()

    def list_cache_stats(self) -> list[dict[str, Any]]:
        rows = self._fetch_all(
            """
            SELECT stage, COUNT(*) AS count FROM cache_entries
            GROUP BY stage
            ORDER BY stage
            """
        )
        return [dict(row) for row in rows]

    def list_cache_entries_older_than(self, cutoff: datetime) -> list[CacheEntry]:
        rows = self._fetch_all(
            "SELECT * FROM cache_entries WHERE created_at < ?",
            (cutoff.isoformat(),),
        )
        return [_row_to_cache(row) for row in rows]

    def list_run_summaries(self, *, batch_id: str | None = None) -> list[dict[str, Any]]:
        if batch_id:
            rows = self._fetch_all(
                """
                SELECT r.run_id, r.batch_id, r.created_at, r.completed_at, r.runtime_ms,
                       s.overall_risk, s.domain_risks_json, s.citations_count, s.validated_evidence_count
                  FROM runs r
                  LEFT JOIN run_summary s ON s.run_id = r.run_id
                 WHERE r.batch_id = ?
                 ORDER BY r.created_at DESC
                """,
                (batch_id,),
            )
        else:
            rows = self._fetch_all(
                """
                SELECT r.run_id, r.batch_id, r.created_at, r.completed_at, r.runtime_ms,
                       s.overall_risk, s.domain_risks_json, s.citations_count, s.validated_evidence_count
                  FROM runs r
                  LEFT JOIN run_summary s ON s.run_id = r.run_id
                 ORDER BY r.created_at DESC
                """
            )
        return [dict(row) for row in rows]

    def _fetch_one(self, query: str, params: tuple[object, ...] = ()) -> sqlite3.Row | None:
        with self._connect() as conn:
            cur = conn.execute(query, params)
            return cur.fetchone()

    def _fetch_all(self, query: str, params: tuple[object, ...] = ()) -> list[sqlite3.Row]:
        with self._connect() as conn:
            cur = conn.execute(query, params)
            return cur.fetchall()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _from_iso(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _row_to_document(row: sqlite3.Row) -> DocumentRecord:
    return DocumentRecord(
        doc_id=row["doc_id"],
        sha256=row["sha256"],
        filename=row["filename"],
        bytes=row["bytes"],
        created_at=_from_iso(row["created_at"]),
    )


def _row_to_cache(row: sqlite3.Row) -> CacheEntry:
    return CacheEntry(
        cache_key=row["cache_key"],
        stage=row["stage"],
        content_hash=row["content_hash"],
        path=row["path"],
        created_at=_from_iso(row["created_at"]),
        last_accessed=_from_iso(row["last_accessed"]) if row["last_accessed"] else None,
    )


__all__ = ["SqliteStore"]
