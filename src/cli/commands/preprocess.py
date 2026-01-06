"""Preprocess debug commands."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import typer

from schemas.internal.documents import DocStructure
from .shared import emit_json, load_doc_structure


app = typer.Typer(
    help="预处理调试",
    context_settings={"help_option_names": ["-h", "--help"]},
    add_completion=False,
    no_args_is_help=True,
    options_metavar="[选项]",
    subcommand_metavar="命令 [参数]",
)


def _truncate_text(text: str, max_chars: int) -> tuple[str, bool]:
    if max_chars <= 0 or len(text) <= max_chars:
        return text, False
    return text[: max_chars - 3] + "...", True


def _trim_doc_structure(
    doc_structure: DocStructure,
    *,
    include_body: bool,
    include_sections: bool,
    max_body_chars: int,
    max_section_chars: int,
    section_limit: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    payload = doc_structure.model_dump()
    truncated = {"body": False, "sections": False, "section_text": False}

    if not include_body:
        payload.pop("body", None)
    else:
        body, body_truncated = _truncate_text(
            str(payload.get("body", "")), max_body_chars
        )
        payload["body"] = body
        truncated["body"] = body_truncated

    if not include_sections:
        payload.pop("sections", None)
    else:
        sections = list(payload.get("sections") or [])
        original_count = len(sections)
        if section_limit > 0:
            sections = sections[:section_limit]
            truncated["sections"] = len(sections) < original_count
        trimmed_sections: list[dict[str, Any]] = []
        for item in sections:
            if not isinstance(item, dict):
                continue
            if max_section_chars > 0 and "text" in item:
                text, text_truncated = _truncate_text(
                    str(item.get("text", "")), max_section_chars
                )
                item = {**item, "text": text}
                truncated["section_text"] = truncated["section_text"] or text_truncated
            trimmed_sections.append(item)
        payload["sections"] = trimmed_sections

    stats = {
        "body_chars": len(doc_structure.body or ""),
        "section_count": len(doc_structure.sections),
        "included": {"body": include_body, "sections": include_sections},
        "truncated": truncated,
        "section_limit": section_limit if section_limit > 0 else None,
        "max_body_chars": max_body_chars if max_body_chars > 0 else None,
        "max_section_chars": max_section_chars if max_section_chars > 0 else None,
    }
    return payload, stats


def _print_summary(doc_structure: DocStructure, stats: dict[str, Any]) -> None:
    lines = [
        "预处理完成",
        f"body 字符数: {stats['body_chars']}",
        f"sections 数量: {stats['section_count']}",
    ]
    truncated = stats.get("truncated") or {}
    if any(truncated.values()):
        flags = []
        if truncated.get("body"):
            flags.append("body")
        if truncated.get("sections"):
            flags.append("sections")
        if truncated.get("section_text"):
            flags.append("section_text")
        lines.append(f"已截断: {', '.join(flags)}")

    titles: list[str] = []
    for span in doc_structure.sections[:5]:
        if span.title:
            titles.append(span.title)
    if titles:
        lines.append("示例标题:")
        lines.extend(f"- {title}" for title in titles)
    typer.echo("\n".join(lines))


@app.command("show", help="输出预处理结果")
def show_preprocess(
    pdf_path: Path = typer.Argument(
        ...,
        exists=True,
        dir_okay=False,
        readable=True,
        metavar="PDF路径",
    ),
    include_body: bool = typer.Option(
        True,
        "--body/--no-body",
        help="输出 body 文本",
    ),
    include_sections: bool = typer.Option(
        True,
        "--sections/--no-sections",
        help="输出 sections 列表",
    ),
    section_limit: int = typer.Option(
        0,
        "--section-limit",
        help="限制输出的段落数量（0 表示不限制）",
    ),
    max_body_chars: int = typer.Option(
        0,
        "--max-body-chars",
        help="body 最大字符数（0 表示不截断）",
    ),
    max_section_chars: int = typer.Option(
        0,
        "--max-section-chars",
        help="单段文本最大字符数（0 表示不截断）",
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        help="写入 JSON 文件路径",
    ),
    json_out: bool = typer.Option(False, "--json", help="输出 JSON"),
) -> None:
    doc_structure = load_doc_structure(pdf_path)
    payload, stats = _trim_doc_structure(
        doc_structure,
        include_body=include_body,
        include_sections=include_sections,
        max_body_chars=max_body_chars,
        max_section_chars=max_section_chars,
        section_limit=section_limit,
    )
    data = {"doc_structure": payload, "stats": stats}

    if output is not None:
        output.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        typer.echo(f"已写入: {output}")
        if not json_out:
            _print_summary(doc_structure, stats)
            return

    if json_out:
        emit_json(data)
        return

    _print_summary(doc_structure, stats)


__all__ = ["app"]
