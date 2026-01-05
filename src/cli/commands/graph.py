"""Graph inspection commands."""

from __future__ import annotations

from pathlib import Path

import typer

from pipelines.graphs.rob2_graph import build_rob2_graph
from schemas.requests import Rob2Input
from services.rob2_runner import run_rob2
from cli.common import build_options, emit_json, load_options_payload


app = typer.Typer(
    help="查看或运行 LangGraph 图",
    context_settings={"help_option_names": ["-h", "--help"]},
    add_completion=False,
    no_args_is_help=True,
    options_metavar="[选项]",
    subcommand_metavar="命令 [参数]",
)


@app.command("show", help="输出图结构")
def show_graph(
    format: str = typer.Option(
        "mermaid",
        "--format",
        help="输出格式：mermaid|ascii|nodes",
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        help="输出文件路径（可选）",
    ),
) -> None:
    graph = build_rob2_graph().get_graph()
    fmt = format.strip().lower()

    if fmt == "nodes":
        lines: list[str] = []
        lines.append("Nodes:")
        for node in graph.nodes.values():
            lines.append(f"- {node.id} ({node.name})")
        lines.append("\nEdges:")
        for edge in graph.edges:
            label = f" [{edge.data}]" if edge.data else ""
            flag = " conditional" if edge.conditional else ""
            lines.append(f"- {edge.source} -> {edge.target}{label}{flag}")
        content = "\n".join(lines)
    elif fmt == "ascii":
        try:
            content = graph.draw_ascii()
        except ImportError:
            raise typer.BadParameter("ASCII 视图需要安装 grandalf：pip install grandalf")
    else:
        content = graph.draw_mermaid()

    if output is None:
        typer.echo(content)
        return

    output.write_text(content, encoding="utf-8")
    typer.echo(f"已写入: {output}")


@app.command("run", help="运行图并输出结果")
def run_graph(
    pdf_path: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True),
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
    options_obj = build_options(payload)
    result = run_rob2(Rob2Input(pdf_path=str(pdf_path)), options_obj)

    if json_out:
        emit_json(result.model_dump())
    if table and getattr(result, "table_markdown", ""):
        typer.echo(result.table_markdown)


__all__ = ["app"]
