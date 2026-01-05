"""Shared helpers for CLI commands."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import typer
from pydantic import ValidationError

from schemas.requests import Rob2RunOptions


def load_options_payload(
    options: str | None,
    options_file: Path | None,
    set_values: list[str] | None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {}

    if options:
        payload.update(_parse_json_string(options))

    if options_file:
        payload.update(_load_options_file(options_file))

    if set_values:
        payload.update(_parse_set_values(set_values))

    return payload


def build_options(payload: dict[str, Any]) -> Rob2RunOptions:
    try:
        return Rob2RunOptions.model_validate(payload)
    except ValidationError as exc:
        raise typer.BadParameter(str(exc)) from exc


def parse_value(value: str) -> Any:
    if value == "":
        return ""
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def emit_json(data: Any) -> None:
    typer.echo(json.dumps(data, ensure_ascii=False, indent=2))


def _parse_json_string(text: str) -> dict[str, Any]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise typer.BadParameter(f"Invalid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise typer.BadParameter("Options must be a JSON object.")
    return data


def _load_options_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise typer.BadParameter(f"Options file not found: {path}")
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in {".yaml", ".yml"}:
        try:
            import yaml
        except Exception as exc:
            raise typer.BadParameter("PyYAML is required for YAML options.") from exc
        data = yaml.safe_load(text) or {}
    else:
        data = _parse_json_string(text)
    if not isinstance(data, dict):
        raise typer.BadParameter("Options file must contain a JSON/YAML object.")
    return data


def _parse_set_values(items: list[str]) -> dict[str, Any]:
    parsed: dict[str, Any] = {}
    for item in items:
        if "=" not in item:
            raise typer.BadParameter("--set requires key=value syntax.")
        key, raw_value = item.split("=", 1)
        key = key.strip()
        if not key:
            raise typer.BadParameter("--set requires a non-empty key.")
        parsed[key] = parse_value(raw_value.strip())
    return parsed

