"""Typer CLI entrypoint for ROB2 runs."""

from __future__ import annotations

from pathlib import Path

import typer

from eagent import __version__
from cli.i18n import apply_cli_localization
from schemas.requests import Rob2Input
from schemas.responses import Rob2RunResult
from services.rob2_runner import run_rob2
from cli.common import (
    build_options,
    emit_json,
    load_options_payload,
    write_run_output_dir,
)
from cli.commands import (
    audit as audit_command,
    batch as batch_command,
    cache as cache_command,
    config as config_command,
    fusion as fusion_command,
    graph as graph_command,
    locator as locator_command,
    playground as playground_command,
    preprocess as preprocess_command,
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
app.add_typer(batch_command.app, name="batch")
app.add_typer(fusion_command.app, name="fusion")
app.add_typer(locator_command.app, name="locator")
app.add_typer(audit_command.app, name="audit")
app.add_typer(cache_command.app, name="cache")
app.add_typer(preprocess_command.app, name="preprocess")
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
    set_values: list[str] | None = typer.Option(
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
    include: list[str] = typer.Option(
        None,
        "--include",
        help="额外输出项：reports|audit_reports|debug|debug_full|table",
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
    output_dir: Path | None = typer.Option(
        None,
        "--output-dir",
        help="输出目录（写入 result.json/table.md 等；默认: ./results）",
    ),
    persist: bool = typer.Option(
        True,
        "--persist/--no-persist",
        help="写入持久化运行记录与分析包",
    ),
    persist_dir: Path | None = typer.Option(
        None,
        "--persist-dir",
        help="持久化根目录（默认使用配置项）",
    ),
    persist_scope: str | None = typer.Option(
        None,
        "--persist-scope",
        help="持久化范围（analysis 等）",
    ),
    batch_id: str | None = typer.Option(
        None,
        "--batch-id",
        help="绑定已有批次 ID",
    ),
    batch_name: str | None = typer.Option(
        None,
        "--batch-name",
        help="创建新批次并绑定",
    ),
    cache_dir: Path | None = typer.Option(
        None,
        "--cache-dir",
        help="缓存根目录（默认使用配置项）",
    ),
    cache_scope: str | None = typer.Option(
        None,
        "--cache-scope",
        help="缓存范围（deterministic|none）",
    ),
    html: bool = typer.Option(
        False,
        "--html",
        help="生成交互式 HTML 报告 (需要 --output-dir)",
    ),
    docx: bool = typer.Option(
        False,
        "--docx",
        help="生成 Word 报告 (需要 --output-dir)",
    ),
    pdf: bool = typer.Option(
        False,
        "--pdf",
        help="生成 PDF 报告 (需要 --output-dir)",
    ),
) -> None:
    if output_dir is None:
        output_dir = Path("results")

    if (html or docx or pdf) and output_dir is None:
        typer.echo("Error: --output-dir is required when generating reports.")
        raise typer.Exit(code=1)

    payload = load_options_payload(options, options_file, set_values)
    payload.setdefault("debug_level", debug)
    if include_reports is not None:
        payload["include_reports"] = include_reports
    if include_audit_reports is not None:
        payload["include_audit_reports"] = include_audit_reports
    include_set = _normalize_include(include)
    if include_set:
        if "reports" in include_set:
            payload["include_reports"] = True
        if "audit_reports" in include_set or "audit" in include_set:
            payload["include_audit_reports"] = True
        if "debug_full" in include_set:
            payload["debug_level"] = "full"
        elif "debug" in include_set:
            payload["debug_level"] = "min"
        if "table" in include_set:
            table = True

    options_obj = build_options(payload)
    result = run_rob2(
        Rob2Input(pdf_path=str(pdf_path)),
        options_obj,
        persist_enabled=persist,
        persistence_dir=str(persist_dir) if persist_dir else None,
        persistence_scope=persist_scope,
        cache_dir=str(cache_dir) if cache_dir else None,
        cache_scope=cache_scope,
        batch_id=batch_id,
        batch_name=batch_name,
    )
    _emit_result(result, json_out=json_out, table=table)
    _write_output_dir(
        result,
        output_dir,
        include_table=table,
        html=html,
        docx=docx,
        pdf=pdf,
        pdf_name=pdf_path.name,
    )


def _emit_result(result: Rob2RunResult, *, json_out: bool, table: bool) -> None:
    if json_out:
        emit_json(result.model_dump())

    if table and getattr(result, "table_markdown", ""):
        typer.echo(result.table_markdown)


def _normalize_include(values: list[str] | None) -> set[str]:
    if not values:
        return set()
    normalized = {value.strip().lower().replace("-", "_") for value in values if value}
    allowed = {"reports", "audit_reports", "audit", "debug", "debug_full", "table"}
    unknown = sorted(normalized - allowed)
    if unknown:
        raise typer.BadParameter(f"--include 不支持: {', '.join(unknown)}")
    return normalized


def _write_output_dir(
    result: Rob2RunResult,
    output_dir: Path,
    *,
    include_table: bool,
    html: bool = False,
    docx: bool = False,
    pdf: bool = False,
    pdf_name: str = "Unknown",
) -> None:
    write_run_output_dir(
        result,
        output_dir,
        include_table=include_table,
        html=html,
        docx=docx,
        pdf=pdf,
        pdf_name=pdf_name,
    )


def main() -> None:
    app()


__all__ = ["app", "main"]
