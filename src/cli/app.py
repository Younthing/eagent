"""Typer CLI entrypoint for ROB2 runs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import typer
from pydantic import ValidationError

from eagent import __version__
from schemas.requests import Rob2Input, Rob2RunOptions
from services.rob2_runner import run_rob2

app = typer.Typer(
    help="ROB2 命令行工具",
    context_settings={"help_option_names": ["-h", "--help"]},
    invoke_without_command=True,
)


@app.callback()
def root(
    ctx: typer.Context,
    version_flag: bool = typer.Option(
        False,
        "-v",
        "--version",
        help="输出版本信息。",
    ),
) -> None:
    if version_flag:
        typer.echo(__version__)
        raise typer.Exit()
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
        raise typer.Exit()


@app.command()
def run(
    pdf_path: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True),
    options: str | None = typer.Option(
        None,
        "--options",
        help="Rob2RunOptions 的 JSON 字符串。",
    ),
    options_file: Path | None = typer.Option(
        None,
        "--options-file",
        help="包含 Rob2RunOptions 的 JSON/YAML 文件路径。",
    ),
    set_values: list[str] = typer.Option(
        None,
        "--set",
        help="使用 key=value 覆盖单个选项，可重复传入。",
    ),
    debug: str = typer.Option(
        "none",
        "--debug",
        help="调试级别：none|min|full。",
    ),
    include_reports: bool | None = typer.Option(
        None,
        "--include-reports/--no-include-reports",
        help="JSON 输出中包含验证报告。",
    ),
    include_audit_reports: bool | None = typer.Option(
        None,
        "--include-audit-reports/--no-include-audit-reports",
        help="JSON 输出中包含审计报告。",
    ),
    json_out: bool = typer.Option(
        False,
        "--json",
        help="输出 JSON 结果。",
    ),
    table: bool = typer.Option(
        True,
        "--table/--no-table",
        help="输出 ROB2 Markdown 表格。",
    ),
) -> None:
    payload = _load_options_payload(options, options_file, set_values)
    payload.setdefault("debug_level", debug)
    if include_reports is not None:
        payload["include_reports"] = include_reports
    if include_audit_reports is not None:
        payload["include_audit_reports"] = include_audit_reports

    try:
        options_obj = Rob2RunOptions.model_validate(payload)
    except ValidationError as exc:
        raise typer.BadParameter(str(exc)) from exc

    result = run_rob2(Rob2Input(pdf_path=str(pdf_path)), options_obj)
    _emit_result(result, json_out=json_out, table=table)


def _load_options_payload(
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


def _parse_json_string(text: str) -> dict[str, Any]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise typer.BadParameter(f"Invalid JSON in --options: {exc}") from exc
    if not isinstance(data, dict):
        raise typer.BadParameter("--options must be a JSON object.")
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
        parsed[key] = _parse_value(raw_value.strip())
    return parsed


def _parse_value(value: str) -> Any:
    if value == "":
        return ""
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def _emit_result(result: Any, *, json_out: bool, table: bool) -> None:
    if json_out:
        payload = result.model_dump()
        typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))

    if table and getattr(result, "table_markdown", ""):
        typer.echo(result.table_markdown)


def main() -> None:
    app()


__all__ = ["app", "main"]
