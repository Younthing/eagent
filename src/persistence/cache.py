"""Deterministic cache manager for preprocessing and retrieval."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

import numpy as np

from persistence.hashing import sha256_bytes
from persistence.sqlite_store import SqliteStore
from persistence.models import CacheEntry


_DETERMINISTIC_STAGES = {
    "preprocess",
    "bm25_index",
    "splade_doc_vectors",
}


@dataclass(frozen=True)
class CachePayload:
    stage: str
    key: str
    path: Path


class CacheManager:
    def __init__(self, base_dir: str | Path, store: SqliteStore, *, scope: str = "deterministic") -> None:
        self._base_dir = Path(base_dir)
        self._cache_dir = self._base_dir / "cache"
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._store = store
        self._scope = scope.strip().lower() if scope else "none"

    @property
    def scope(self) -> str:
        return self._scope

    def enabled_for(self, stage: str) -> bool:
        if self._scope == "none":
            return False
        if self._scope == "deterministic":
            return stage in _DETERMINISTIC_STAGES
        return False

    def get_json(self, *, stage: str, key: str) -> dict[str, Any] | None:
        if not self.enabled_for(stage):
            return None
        entry = self._store.get_cache_entry(stage=stage, cache_key=key)
        if entry is None:
            return None
        path = Path(entry.path)
        if not path.exists():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        self._store.touch_cache_entry(stage=stage, cache_key=key)
        return payload

    def set_json(self, *, stage: str, key: str, payload: dict[str, Any]) -> CacheEntry:
        if not self.enabled_for(stage):
            raise ValueError(f"Cache stage not enabled: {stage}")
        path = self._cache_path(stage, key, "json")
        path.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2)
        path.write_text(text, encoding="utf-8")
        entry = CacheEntry(
            cache_key=key,
            stage=stage,
            content_hash=sha256_bytes(text.encode("utf-8")),
            path=str(path),
            created_at=datetime.now(timezone.utc),
            last_accessed=None,
        )
        self._store.put_cache_entry(entry)
        return entry

    def get_numpy(self, *, stage: str, key: str) -> np.ndarray | None:
        if not self.enabled_for(stage):
            return None
        entry = self._store.get_cache_entry(stage=stage, cache_key=key)
        if entry is None:
            return None
        path = Path(entry.path)
        if not path.exists():
            return None
        data = np.load(path)
        self._store.touch_cache_entry(stage=stage, cache_key=key)
        return data

    def set_numpy(self, *, stage: str, key: str, array: np.ndarray) -> CacheEntry:
        if not self.enabled_for(stage):
            raise ValueError(f"Cache stage not enabled: {stage}")
        path = self._cache_path(stage, key, "npy")
        path.parent.mkdir(parents=True, exist_ok=True)
        np.save(path, array)
        content_hash = sha256_bytes(path.read_bytes())
        entry = CacheEntry(
            cache_key=key,
            stage=stage,
            content_hash=content_hash,
            path=str(path),
            created_at=datetime.now(timezone.utc),
            last_accessed=None,
        )
        self._store.put_cache_entry(entry)
        return entry

    def stats(self) -> list[dict[str, Any]]:
        return self._store.list_cache_stats()

    def prune_older_than(self, *, days: int) -> int:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        entries = self._store.list_cache_entries_older_than(cutoff)
        removed = 0
        for entry in entries:
            path = Path(entry.path)
            if path.exists():
                path.unlink()
            self._store.delete_cache_entry(stage=entry.stage, cache_key=entry.cache_key)
            removed += 1
        return removed

    def _cache_path(self, stage: str, key: str, ext: str) -> Path:
        cleaned_ext = ext.lstrip(".") or "bin"
        return self._cache_dir / stage / f"{key}.{cleaned_ext}"


__all__ = ["CacheManager"]
