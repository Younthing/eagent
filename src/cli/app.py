"""Typer CLI entrypoint for ROB2 runs."""

from __future__ import annotations

from pathlib import Path

import typer

from eagent import __version__
from cli.i18n import apply_cli_localization
from schemas.requests import Rob2Input
from schemas.responses import Rob2RunResult
from services.rob2_runner import run_rob2
from cli.common import build_options, emit_json, load_options_payload
from cli.commands import (
    audit as audit_command,
    cache as cache_command,
    config as config_command,
    fusion as fusion_command,
    graph as graph_command,
    locator as locator_command,
    playground as playground_command,
    questions as questions_command,
    retrieval as retrieval_command,
    validate as validate_command,
)

apply_cli_localization()

app = typer.Typer(
    help=(
        "ROB2 命令行工具\n\n用于运行 ROB2 评估流程并进行检索、验证、审计和图结构调试\n"
    ),
    context_settings={"help_option_names": ["-h", "--help"]},
    invoke_without_command=True,
    add_completion=False,
    options_metavar="[选项]",
    subcommand_metavar="命令 [参数]",
)

app.add_typer(config_command.app, name="config")
app.add_typer(questions_command.app, name="questions")
app.add_typer(graph_command.app, name="graph")
app.add_typer(validate_command.app, name="validate")
app.add_typer(retrieval_command.app, name="retrieval")
app.add_typer(fusion_command.app, name="fusion")
app.add_typer(locator_command.app, name="locator")
app.add_typer(audit_command.app, name="audit")
app.add_typer(cache_command.app, name="cache")
app.add_typer(playground_command.app, name="playground")


@app.callback()
def root(
    ctx: typer.Context,
    version_flag: bool = typer.Option(
        False,
        "-v",
        "--version",
        help="输出版本信息",
    ),
) -> None:
    if version_flag:
        typer.echo(__version__)
        raise typer.Exit()
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
        raise typer.Exit()


@app.command(help="运行 ROB2 全流程并输出结果")
def run(
    pdf_path: Path = typer.Argument(
        ...,
        exists=True,
        dir_okay=False,
        readable=True,
        metavar="PDF路径",
    ),
    options: str | None = typer.Option(
        None,
        "--options",
        help="Rob2RunOptions 的 JSON 字符串",
    ),
    options_file: Path | None = typer.Option(
        None,
        "--options-file",
        help="包含 Rob2RunOptions 的 JSON/YAML 文件路径",
    ),
    set_values: list[str] = typer.Option(
        None,
        "--set",
        help="使用 key=value 覆盖单个选项，可重复传入",
    ),
    debug: str = typer.Option(
        "none",
        "--debug",
        help="调试级别：none|min|full",
    ),
    include_reports: bool | None = typer.Option(
        None,
        "--include-reports/--no-include-reports",
        help="JSON 输出中包含验证报告",
    ),
    include_audit_reports: bool | None = typer.Option(
        None,
        "--include-audit-reports/--no-include-audit-reports",
        help="JSON 输出中包含审计报告",
    ),
    json_out: bool = typer.Option(
        False,
        "--json",
        help="输出 JSON 结果",
    ),
    table: bool = typer.Option(
        True,
        "--table/--no-table",
        help="输出 ROB2 Markdown 表格",
    ),
) -> None:
    payload = load_options_payload(options, options_file, set_values)
    payload.setdefault("debug_level", debug)
    if include_reports is not None:
        payload["include_reports"] = include_reports
    if include_audit_reports is not None:
        payload["include_audit_reports"] = include_audit_reports

    options_obj = build_options(payload)
    result = run_rob2(Rob2Input(pdf_path=str(pdf_path)), options_obj)
    _emit_result(result, json_out=json_out, table=table)


def _emit_result(result: Rob2RunResult, *, json_out: bool, table: bool) -> None:
    if json_out:
        emit_json(result.model_dump())

    if table and getattr(result, "table_markdown", ""):
        typer.echo(result.table_markdown)


def main() -> None:
    app()


__all__ = ["app", "main"]
