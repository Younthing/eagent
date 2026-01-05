"""Domain audit commands."""

from __future__ import annotations

from pathlib import Path

import typer

from schemas.requests import Rob2Input
from services.rob2_runner import run_rob2
from cli.common import build_options, emit_json, load_options_payload


app = typer.Typer(
    help="领域审计调试",
    context_settings={"help_option_names": ["-h", "--help"]},
    add_completion=False,
    no_args_is_help=True,
    options_metavar="[选项]",
    subcommand_metavar="命令 [参数]",
)


@app.command("run", help="运行领域审计")
def run_audit(
    pdf_path: Path = typer.Argument(
        ...,
        exists=True,
        dir_okay=False,
        readable=True,
        metavar="PDF路径",
    ),
    mode: str = typer.Option("llm", "--mode", help="审计模式：llm|none"),
    audit_window: int | None = typer.Option(None, "--audit-window", help="证据补丁窗口"),
    audit_rerun: bool | None = typer.Option(
        None,
        "--audit-rerun/--no-audit-rerun",
        help="审计后是否重跑领域",
    ),
    audit_final: bool | None = typer.Option(
        None,
        "--audit-final/--no-audit-final",
        help="是否执行最终全域审计",
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
    json_out: bool = typer.Option(False, "--json", help="输出 JSON"),
    table: bool = typer.Option(True, "--table/--no-table", help="输出 ROB2 表格"),
) -> None:
    payload = load_options_payload(options, options_file, set_values)
    payload["domain_audit_mode"] = mode
    if audit_window is not None:
        payload["domain_audit_patch_window"] = audit_window
    if audit_rerun is not None:
        payload["domain_audit_rerun_domains"] = audit_rerun
    if audit_final is not None:
        payload["domain_audit_final"] = audit_final

    options_obj = build_options(payload)
    result = run_rob2(Rob2Input(pdf_path=str(pdf_path)), options_obj)

    if json_out:
        emit_json(result.model_dump())
    if table and getattr(result, "table_markdown", ""):
        typer.echo(result.table_markdown)


__all__ = ["app"]
