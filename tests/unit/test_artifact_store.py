from pathlib import Path

from persistence.fs_store import FsArtifactStore


def test_artifact_store_writes_and_links(tmp_path: Path) -> None:
    store = FsArtifactStore(tmp_path)
    record = store.write_json({"hello": "world"})
    artifact_path = Path(record.path)

    assert artifact_path.exists()
    assert artifact_path.read_text(encoding="utf-8").strip().startswith("{")

    link_path = store.link_run_artifact("run_test", name="result.json", artifact=record)
    assert link_path.exists()
    assert link_path.read_text(encoding="utf-8").strip().startswith("{")
