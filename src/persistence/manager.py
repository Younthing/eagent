"""Persistence manager for runs and artifacts."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4

from eagent import __version__ as _code_version
from persistence.fs_store import FsArtifactStore
from persistence.hashing import hash_payload
from persistence.models import RunRecord, RunSummaryRecord
from persistence.sqlite_store import SqliteStore


@dataclass(frozen=True)
class RunContext:
    run_id: str
    doc_id: str | None
    batch_id: str | None
    run_dir: Path


class PersistenceManager:
    def __init__(self, base_dir: str | Path, *, scope: str = "analysis") -> None:
        self._base_dir = Path(base_dir)
        self._scope = scope.strip().lower() if scope else "analysis"
        self._store = SqliteStore(self._base_dir / "metadata.sqlite")
        self._artifacts = FsArtifactStore(self._base_dir)

    @property
    def scope(self) -> str:
        return self._scope

    @property
    def base_dir(self) -> Path:
        return self._base_dir

    @property
    def store(self) -> SqliteStore:
        return self._store

    @property
    def artifacts(self) -> FsArtifactStore:
        return self._artifacts

    def start_run(
        self,
        *,
        doc_hash: str,
        filename: str | None,
        bytes_size: int | None,
        options_payload: Mapping[str, Any],
        batch_id: str | None = None,
        batch_name: str | None = None,
    ) -> RunContext:
        document = self._store.create_document(
            sha256=doc_hash,
            filename=filename,
            bytes_size=bytes_size,
        )
        batch = None
        if batch_name and not batch_id:
            batch = self._store.create_batch(name=batch_name, metadata=None)
            batch_id = batch.batch_id

        run_id = _new_run_id()
        now = datetime.now(timezone.utc)
        options_json = json.dumps(options_payload, ensure_ascii=False, sort_keys=True)
        options_hash = hash_payload(options_payload)
        record = RunRecord(
            run_id=run_id,
            doc_id=document.doc_id if document else None,
            batch_id=batch_id,
            status="running",
            created_at=now,
            completed_at=None,
            options_json=options_json,
            options_hash=options_hash,
            code_version=_code_version,
            question_set_version=None,
            runtime_ms=None,
            warnings_json=None,
        )
        self._store.create_run(record)
        run_dir = self._artifacts.ensure_run_dir(run_id)
        return RunContext(run_id=run_id, doc_id=document.doc_id if document else None, batch_id=batch_id, run_dir=run_dir)

    def persist_artifacts(
        self,
        *,
        run_ctx: RunContext,
        result_payload: dict[str, Any],
        table_markdown: str | None,
        manifest: dict[str, Any],
        doc_structure: dict | None,
        question_set: dict | None,
        validated_candidates: dict | None,
        validation_reports: dict | None,
        audit_reports: list[dict] | None,
    ) -> None:
        artifacts = []

        manifest_record = self._artifacts.write_json(manifest)
        self._store.insert_artifact(manifest_record)
        self._store.link_artifact(
            run_id=run_ctx.run_id,
            artifact_id=manifest_record.artifact_id,
            artifact_type="run_manifest",
        )
        self._artifacts.link_run_artifact(run_ctx.run_id, name="run_manifest.json", artifact=manifest_record)
        artifacts.append(manifest_record)

        result_record = self._artifacts.write_json(result_payload)
        self._store.insert_artifact(result_record)
        self._store.link_artifact(
            run_id=run_ctx.run_id,
            artifact_id=result_record.artifact_id,
            artifact_type="result",
        )
        self._artifacts.link_run_artifact(run_ctx.run_id, name="result.json", artifact=result_record)
        artifacts.append(result_record)

        if table_markdown:
            table_record = self._artifacts.write_text(table_markdown, ext="md")
            self._store.insert_artifact(table_record)
            self._store.link_artifact(
                run_id=run_ctx.run_id,
                artifact_id=table_record.artifact_id,
                artifact_type="table",
            )
            self._artifacts.link_run_artifact(run_ctx.run_id, name="table.md", artifact=table_record)
            artifacts.append(table_record)

        if doc_structure is not None:
            doc_record = self._artifacts.write_json(doc_structure)
            self._store.insert_artifact(doc_record)
            self._store.link_artifact(
                run_id=run_ctx.run_id,
                artifact_id=doc_record.artifact_id,
                artifact_type="doc_structure",
            )
            self._artifacts.link_run_artifact(run_ctx.run_id, name="doc_structure.json", artifact=doc_record)

        if question_set is not None:
            qs_record = self._artifacts.write_json(question_set)
            self._store.insert_artifact(qs_record)
            self._store.link_artifact(
                run_id=run_ctx.run_id,
                artifact_id=qs_record.artifact_id,
                artifact_type="question_set",
            )
            self._artifacts.link_run_artifact(run_ctx.run_id, name="question_set.json", artifact=qs_record)

        if validated_candidates is not None:
            vc_record = self._artifacts.write_json(validated_candidates)
            self._store.insert_artifact(vc_record)
            self._store.link_artifact(
                run_id=run_ctx.run_id,
                artifact_id=vc_record.artifact_id,
                artifact_type="validated_candidates",
            )
            self._artifacts.link_run_artifact(run_ctx.run_id, name="validated_candidates.json", artifact=vc_record)

        if validation_reports is not None:
            vr_record = self._artifacts.write_json(validation_reports)
            self._store.insert_artifact(vr_record)
            self._store.link_artifact(
                run_id=run_ctx.run_id,
                artifact_id=vr_record.artifact_id,
                artifact_type="validation_reports",
            )
            self._artifacts.link_run_artifact(run_ctx.run_id, name="validation_reports.json", artifact=vr_record)

        if audit_reports is not None:
            ar_record = self._artifacts.write_json(audit_reports)
            self._store.insert_artifact(ar_record)
            self._store.link_artifact(
                run_id=run_ctx.run_id,
                artifact_id=ar_record.artifact_id,
                artifact_type="audit_reports",
            )
            self._artifacts.link_run_artifact(run_ctx.run_id, name="audit_reports.json", artifact=ar_record)

    def finalize_run(
        self,
        *,
        run_ctx: RunContext,
        result_payload: dict[str, Any],
        summary: RunSummaryRecord,
        runtime_ms: int | None,
        warnings: list[str],
        question_set_version: str | None,
    ) -> None:
        warnings_json = json.dumps(warnings, ensure_ascii=False)
        self._store.update_run(
            run_ctx.run_id,
            status="completed",
            completed_at=datetime.now(timezone.utc),
            runtime_ms=runtime_ms,
            question_set_version=question_set_version,
            warnings_json=warnings_json,
        )
        self._store.insert_run_summary(summary)


def build_manifest(
    *,
    run_id: str,
    doc_hash: str,
    options_payload: Mapping[str, Any],
    state_config: Mapping[str, Any],
    question_set_version: str | None,
) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "doc_hash": doc_hash,
        "options": dict(options_payload),
        "state_config": dict(state_config),
        "code_version": _code_version,
        "question_set_version": question_set_version,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def _new_run_id() -> str:
    return f"run_{uuid4().hex}"


__all__ = ["PersistenceManager", "RunContext", "build_manifest"]
