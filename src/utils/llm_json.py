"""Helpers for extracting JSON objects from LLM output."""

from __future__ import annotations

import json
import re
from typing import Iterator

_CODE_BLOCK_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


def extract_json_object(text: str, *, prefer_code_block: bool = True) -> str:
    """Extract the first valid JSON object string from text.

    Strategy:
    - If prefer_code_block is True, scan code blocks first.
    - Otherwise scan the full text.
    - Candidate objects are validated via json.loads and must decode to dict.
    """

    source = text or ""
    if prefer_code_block:
        for block in _iter_code_blocks(source):
            candidate = _extract_first_json_object(block)
            if candidate is not None:
                return candidate

    candidate = _extract_first_json_object(source)
    if candidate is not None:
        return candidate

    raise ValueError("No JSON object found in LLM response")


def _iter_code_blocks(text: str) -> Iterator[str]:
    for match in _CODE_BLOCK_RE.finditer(text):
        yield match.group(1)


def _extract_first_json_object(text: str) -> str | None:
    for start in _iter_open_braces(text):
        end = _find_matching_brace(text, start)
        if end is None:
            continue
        candidate = text[start : end + 1]
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return candidate
    return None


def _iter_open_braces(text: str) -> Iterator[int]:
    idx = 0
    while True:
        idx = text.find("{", idx)
        if idx == -1:
            return
        yield idx
        idx += 1


def _find_matching_brace(text: str, start: int) -> int | None:
    depth = 0
    in_string = False
    escape = False

    for idx in range(start, len(text)):
        char = text[idx]
        if in_string:
            if escape:
                escape = False
                continue
            if char == "\\":
                escape = True
                continue
            if char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
            continue
        if char == "{":
            depth += 1
            continue
        if char == "}":
            depth -= 1
            if depth == 0:
                return idx
    return None


__all__ = ["extract_json_object"]
