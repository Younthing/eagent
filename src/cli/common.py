"""Shared helpers for CLI commands."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import typer
from pydantic import ValidationError

from schemas.requests import Rob2RunOptions
from schemas.responses import Rob2RunResult


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


def write_run_output_dir(
    result: Rob2RunResult,
    output_dir: Path,
    *,
    include_table: bool,
    html: bool = False,
    docx: bool = False,
    pdf: bool = False,
    pdf_name: str = "Unknown",
) -> None:
    """Persist a single run result to an output directory."""
    output_dir.mkdir(parents=True, exist_ok=True)
    result_path = output_dir / "result.json"
    result_path.write_text(
        json.dumps(result.model_dump(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    if include_table and result.table_markdown:
        (output_dir / "table.md").write_text(result.table_markdown, encoding="utf-8")

    if result.reports is not None:
        (output_dir / "reports.json").write_text(
            json.dumps(result.reports, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    if result.audit_reports is not None:
        (output_dir / "audit_reports.json").write_text(
            json.dumps(result.audit_reports, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    if result.debug is not None:
        (output_dir / "debug.json").write_text(
            json.dumps(result.debug, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    if html or docx or pdf:
        from services.reports import (
            generate_docx_report,
            generate_html_report,
            generate_pdf_report,
        )

        if html:
            generate_html_report(result, output_dir / "report.html", pdf_name)
        if docx:
            generate_docx_report(result, output_dir / "report.docx", pdf_name)
        if pdf:
            generate_pdf_report(result, output_dir / "report.pdf", pdf_name)


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
