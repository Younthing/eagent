"""Hashing helpers for persistence and cache keys."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


def sha256_bytes(data: bytes) -> str:
    """Return hex sha256 of raw bytes."""
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: str | Path, *, chunk_size: int = 1024 * 1024) -> str:
    """Return sha256 of a file by streaming."""
    hasher = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()


def stable_json_dumps(payload: object) -> str:
    """Dump JSON with stable ordering for hashing."""
    return json.dumps(
        payload,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        default=_json_default,
    )


def hash_payload(payload: object) -> str:
    """Return sha256 hash of a JSON-serializable payload."""
    return sha256_bytes(stable_json_dumps(payload).encode("utf-8"))


def preprocess_cache_key(
    doc_hash: str,
    docling_config: Mapping[str, Any],
    doc_scope_config: Mapping[str, Any],
    preprocess_flags: Mapping[str, Any],
    code_version: str | None = None,
) -> str:
    payload = {
        "stage": "preprocess",
        "doc_hash": doc_hash,
        "docling": dict(docling_config),
        "doc_scope": dict(doc_scope_config),
        "preprocess": dict(preprocess_flags),
    }
    if code_version:
        payload["code_version"] = code_version
    return hash_payload(payload)


def bm25_cache_key(
    doc_hash: str,
    tokenizer_config: Mapping[str, Any],
    code_version: str | None = None,
) -> str:
    payload = {
        "stage": "bm25_index",
        "doc_hash": doc_hash,
        "tokenizer": dict(tokenizer_config),
    }
    if code_version:
        payload["code_version"] = code_version
    return hash_payload(payload)


def splade_cache_key(
    doc_hash: str,
    model_id: str,
    doc_max_length: int,
    code_version: str | None = None,
) -> str:
    payload = {
        "stage": "splade_doc_vectors",
        "doc_hash": doc_hash,
        "model_id": model_id,
        "doc_max_length": int(doc_max_length),
    }
    if code_version:
        payload["code_version"] = code_version
    return hash_payload(payload)


def _json_default(value: object) -> str:
    if isinstance(value, Path):
        return str(value)
    return str(value)


__all__ = [
    "bm25_cache_key",
    "hash_payload",
    "preprocess_cache_key",
    "sha256_bytes",
    "sha256_file",
    "splade_cache_key",
    "stable_json_dumps",
]
