from datetime import datetime, timezone
from pathlib import Path

from persistence.models import ArtifactRecord, RunRecord, RunSummaryRecord
from persistence.sqlite_store import SqliteStore


def test_sqlite_store_roundtrip(tmp_path: Path) -> None:
    store = SqliteStore(tmp_path / "metadata.sqlite")

    document = store.create_document(
        sha256="abc",
        filename="file.pdf",
        bytes_size=123,
    )
    assert document.sha256 == "abc"

    run = RunRecord(
        run_id="run_1",
        doc_id=document.doc_id,
        batch_id=None,
        status="running",
        created_at=datetime.now(timezone.utc),
        completed_at=None,
        options_json="{}",
        options_hash="hash",
        code_version="0",
        question_set_version="1.0",
        runtime_ms=None,
        warnings_json=None,
    )
    store.create_run(run)

    artifact = ArtifactRecord(
        artifact_id="artifact_1",
        content_hash="hash",
        type="json",
        path=str(tmp_path / "artifact.json"),
        bytes=10,
        created_at=datetime.now(timezone.utc),
    )
    store.insert_artifact(artifact)
    store.link_artifact(run_id=run.run_id, artifact_id=artifact.artifact_id, artifact_type="result")

    summary = RunSummaryRecord(
        run_id=run.run_id,
        overall_risk="low",
        domain_risks_json="{}",
        citations_count=0,
        validated_evidence_count=0,
    )
    store.insert_run_summary(summary)

    summaries = store.list_run_summaries()
    assert summaries
    assert summaries[0]["run_id"] == "run_1"
