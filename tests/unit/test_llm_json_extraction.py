from __future__ import annotations

import json

import pytest

from utils.llm_json import extract_json_object


def test_extract_json_object_prefers_code_block() -> None:
    text = (
        'prefix {noise} {"outside": true}\n'
        '```json\n'
        '{"inside": 1}\n'
        '```\n'
        '{tail}'
    )
    extracted = extract_json_object(text, prefer_code_block=True)
    payload = json.loads(extracted)
    assert payload == {"inside": 1}


def test_extract_json_object_scans_body_after_invalid_brace() -> None:
    text = 'lead {not json} middle {"ok": 2} tail'
    extracted = extract_json_object(text, prefer_code_block=True)
    payload = json.loads(extracted)
    assert payload == {"ok": 2}


def test_extract_json_object_handles_braces_inside_strings() -> None:
    text = 'prefix {"a": "brace { inside }", "b": 1} trailing'
    extracted = extract_json_object(text, prefer_code_block=True)
    payload = json.loads(extracted)
    assert payload == {"a": "brace { inside }", "b": 1}


def test_extract_json_object_raises_when_missing() -> None:
    with pytest.raises(ValueError, match="No JSON object found"):
        extract_json_object("no json here", prefer_code_block=True)
