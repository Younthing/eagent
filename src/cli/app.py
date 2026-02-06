"""Typer CLI entrypoint for ROB2 runs."""

from __future__ import annotations

import os
import shlex
import sys
from importlib import import_module
from pathlib import Path
from typing import Any

import typer

from eagent import __version__
from cli.i18n import apply_cli_localization

apply_cli_localization()

_SUBCOMMAND_SPECS: list[tuple[str, str, str]] = [
    ("config", "cli.commands.config", "配置查看与导出"),
    ("questions", "cli.commands.questions", "题库查看与导出"),
    ("graph", "cli.commands.graph", "查看或运行 LangGraph 图"),
    ("validate", "cli.commands.validate", "验证层调试"),
    ("retrieval", "cli.commands.retrieval", "检索与召回调试"),
    ("batch", "cli.commands.batch", "批量运行 ROB2"),
    ("fusion", "cli.commands.fusion", "证据融合调试"),
    ("locator", "cli.commands.locator", "证据定位调试"),
    ("audit", "cli.commands.audit", "领域审计调试"),
    ("cache", "cli.commands.cache", "缓存查看与清理"),
    ("preprocess", "cli.commands.preprocess", "预处理调试"),
    ("playground", "cli.commands.playground", "交互式调试工具"),
]
_SUBCOMMAND_NAMES = {name for name, _, _ in _SUBCOMMAND_SPECS}
_SUBCOMMANDS_REGISTERED = False

app = typer.Typer(
    help=(
        "ROB2 命令行工具\n\n用于运行 ROB2 评估流程并进行检索、验证、审计和图结构调试\n"
    ),
    context_settings={"help_option_names": ["-h", "--help"]},
    invoke_without_command=True,
    add_completion=True,
    options_metavar="[选项]",
    subcommand_metavar="命令 [参数]",
)


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
    from cli.common import build_options, load_options_payload
    from schemas.requests import Rob2Input
    from services.rob2_runner import run_rob2

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


def _emit_result(result: Any, *, json_out: bool, table: bool) -> None:
    from cli.common import emit_json

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
    result: Any,
    output_dir: Path,
    *,
    include_table: bool,
    html: bool = False,
    docx: bool = False,
    pdf: bool = False,
    pdf_name: str = "Unknown",
) -> None:
    from cli.common import write_run_output_dir

    write_run_output_dir(
        result,
        output_dir,
        include_table=include_table,
        html=html,
        docx=docx,
        pdf=pdf,
        pdf_name=pdf_name,
    )


def _parse_invoked_subcommand() -> str | None:
    completion_args = os.getenv("_TYPER_COMPLETE_ARGS")
    tokens: list[str]
    if completion_args:
        try:
            tokens = shlex.split(completion_args)
        except ValueError:
            tokens = completion_args.split()
        if tokens:
            tokens = tokens[1:]
    else:
        tokens = sys.argv[1:]

    for token in tokens:
        if token in _SUBCOMMAND_NAMES:
            return token
        if token.startswith("-"):
            continue
        break
    return None


def _register_subcommands() -> None:
    global _SUBCOMMANDS_REGISTERED
    if _SUBCOMMANDS_REGISTERED:
        return

    selected = _parse_invoked_subcommand()
    for name, module_path, help_text in _SUBCOMMAND_SPECS:
        if selected == name:
            module = import_module(module_path)
            app.add_typer(module.app, name=name)
            continue
        app.add_typer(
            typer.Typer(
                help=help_text,
                add_completion=False,
                no_args_is_help=True,
                options_metavar="[选项]",
                subcommand_metavar="命令 [参数]",
            ),
            name=name,
        )

    _SUBCOMMANDS_REGISTERED = True


def main() -> None:
    _register_subcommands()
    app()


__all__ = ["app", "main"]
