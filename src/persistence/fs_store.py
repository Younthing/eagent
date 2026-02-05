"""Filesystem artifact store with content-addressed paths."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from persistence.hashing import sha256_bytes
from persistence.models import ArtifactRecord


class FsArtifactStore:
    def __init__(self, base_dir: str | Path) -> None:
        self._base_dir = Path(base_dir)
        self._artifacts_dir = self._base_dir / "artifacts"
        self._runs_dir = self._base_dir / "runs"
        self._artifacts_dir.mkdir(parents=True, exist_ok=True)
        self._runs_dir.mkdir(parents=True, exist_ok=True)

    @property
    def artifacts_dir(self) -> Path:
        return self._artifacts_dir

    @property
    def runs_dir(self) -> Path:
        return self._runs_dir

    def write_text(self, content: str, *, ext: str) -> ArtifactRecord:
        return self.write_bytes(content.encode("utf-8"), ext=ext)

    def write_json(self, payload: object, *, ext: str = "json") -> ArtifactRecord:
        text = json.dumps(payload, ensure_ascii=False, indent=2)
        return self.write_text(text, ext=ext)

    def write_bytes(self, content: bytes, *, ext: str) -> ArtifactRecord:
        cleaned_ext = ext.lstrip(".") or "bin"
        content_hash = sha256_bytes(content)
        subdir = self._artifacts_dir / content_hash[:2]
        subdir.mkdir(parents=True, exist_ok=True)
        path = subdir / f"{content_hash}.{cleaned_ext}"
        if not path.exists():
            path.write_bytes(content)
        record = ArtifactRecord(
            artifact_id=f"artifact_{content_hash}",
            content_hash=content_hash,
            type=cleaned_ext,
            path=str(path),
            bytes=path.stat().st_size,
            created_at=datetime.now(timezone.utc),
        )
        return record

    def ensure_run_dir(self, run_id: str) -> Path:
        run_dir = self._runs_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        return run_dir

    def link_run_artifact(self, run_id: str, *, name: str, artifact: ArtifactRecord) -> Path:
        run_dir = self.ensure_run_dir(run_id)
        target = Path(artifact.path)
        dest = run_dir / name
        if dest.exists():
            return dest
        try:
            os.link(target, dest)
        except OSError:
            dest.write_bytes(target.read_bytes())
        return dest


__all__ = ["FsArtifactStore"]
