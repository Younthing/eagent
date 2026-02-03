"""Utilities for retry-scoped evidence recomputation."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from schemas.internal.rob2 import QuestionSet


def read_retry_question_ids(state: Mapping[str, Any]) -> set[str] | None:
    """Return retry question IDs when provided, else None."""
    raw = state.get("retry_question_ids")
    if raw is None:
        return None
    if not isinstance(raw, list):
        raise ValueError("retry_question_ids must be a list[str]")

    ids: list[str] = []
    for item in raw:
        if not isinstance(item, str):
            raise ValueError("retry_question_ids must be a list[str]")
        cleaned = item.strip()
        if cleaned:
            ids.append(cleaned)

    return set(ids) if ids else None


def filter_question_set(question_set: QuestionSet, allowed_ids: set[str] | None) -> QuestionSet:
    """Return a QuestionSet filtered to the allowed IDs (or original if None)."""
    if allowed_ids is None:
        return question_set
    filtered = [q for q in question_set.questions if q.question_id in allowed_ids]
    return QuestionSet.model_construct(
        version=question_set.version,
        variant=question_set.variant,
        questions=filtered,
    )


def merge_by_question(
    prev_map: Mapping[str, Any] | None,
    new_map: Mapping[str, Any] | None,
    active_ids: set[str] | None,
) -> dict[str, Any]:
    """Merge question-keyed maps, replacing only active IDs when provided."""
    prev: dict[str, Any] = {
        str(key): value for key, value in (prev_map or {}).items() if isinstance(key, str)
    }
    new: dict[str, Any] = {
        str(key): value for key, value in (new_map or {}).items() if isinstance(key, str)
    }
    if active_ids is None:
        return new

    merged = dict(prev)
    for question_id in active_ids:
        merged[question_id] = new.get(question_id, [])
    return merged


def merge_bundles(
    prev_list: Sequence[Mapping[str, Any]] | None,
    new_list: Sequence[Mapping[str, Any]] | None,
    question_set: QuestionSet,
) -> list[dict]:
    """Merge bundle lists, preferring new entries when present."""
    prev_map = _map_bundles(prev_list)
    new_map = _map_bundles(new_list)

    merged: list[dict] = []
    seen: set[str] = set()
    for question in question_set.questions:
        qid = question.question_id
        bundle = new_map.get(qid) or prev_map.get(qid)
        if bundle is not None:
            merged.append(dict(bundle))
            seen.add(qid)

    extra = sorted((set(prev_map) | set(new_map)) - seen)
    for qid in extra:
        bundle = new_map.get(qid) or prev_map.get(qid)
        if bundle is not None:
            merged.append(dict(bundle))
    return merged


def _map_bundles(items: Sequence[Mapping[str, Any]] | None) -> dict[str, Mapping[str, Any]]:
    mapping: dict[str, Mapping[str, Any]] = {}
    for item in items or []:
        if not isinstance(item, Mapping):
            continue
        qid = item.get("question_id")
        if isinstance(qid, str) and qid.strip():
            mapping[qid] = item
    return mapping


__all__ = [
    "filter_question_set",
    "merge_bundles",
    "merge_by_question",
    "read_retry_question_ids",
]
