"""Preprocess debug commands."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import typer

from schemas.internal.documents import DocStructure
from persistence import CacheManager
from persistence.hashing import sha256_file
from persistence.sqlite_store import SqliteStore
from pipelines.graphs.nodes.preprocess import preprocess_node
from core.config import get_settings
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
    drop_references: bool = typer.Option(
        True,
        "--drop-references/--keep-references",
        help="丢弃参考文献段落",
    ),
    reference_titles: str | None = typer.Option(
        None,
        "--reference-titles",
        help="参考文献标题匹配（逗号分隔）",
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        help="写入 JSON 文件路径",
    ),
    json_out: bool = typer.Option(False, "--json", help="输出 JSON"),
) -> None:
    doc_structure = load_doc_structure(
        pdf_path,
        drop_references=drop_references,
        reference_titles=reference_titles,
    )
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


@app.command("metadata", help="抽取文档元数据")
def extract_metadata(
    pdf_path: Path = typer.Argument(
        ...,
        exists=True,
        dir_okay=False,
        readable=True,
        metavar="PDF路径",
    ),
    mode: str | None = typer.Option(
        None,
        "--mode",
        help="元数据抽取模式（none|llm）",
    ),
    model: str | None = typer.Option(
        None,
        "--model",
        help="元数据抽取模型 ID",
    ),
    max_chars: int | None = typer.Option(
        None,
        "--max-chars",
        help="用于抽取的最大字符数",
    ),
    extraction_passes: int | None = typer.Option(
        None,
        "--passes",
        help="抽取轮次",
    ),
    max_output_tokens: int | None = typer.Option(
        None,
        "--max-output-tokens",
        help="模型最大输出 token",
    ),
    use_cache: bool = typer.Option(
        True,
        "--cache/--no-cache",
        help="是否使用预处理缓存",
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        help="写入 JSON 文件路径",
    ),
    json_out: bool = typer.Option(True, "--json/--no-json", help="输出 JSON"),
) -> None:
    settings = get_settings()
    cache_manager = None
    if use_cache and settings.cache_scope != "none":
        base_dir = Path(settings.cache_dir or settings.persistence_dir)
        store = SqliteStore(base_dir / "metadata.sqlite")
        cache_manager = CacheManager(base_dir, store, scope=settings.cache_scope)

    state: dict[str, Any] = {
        "pdf_path": str(pdf_path),
        "doc_hash": sha256_file(str(pdf_path)),
        "cache_manager": cache_manager,
    }
    if mode is not None:
        state["document_metadata_mode"] = mode
    if model is not None:
        state["document_metadata_model"] = model
    if max_chars is not None:
        state["document_metadata_max_chars"] = max_chars
    if extraction_passes is not None:
        state["document_metadata_extraction_passes"] = extraction_passes
    if max_output_tokens is not None:
        state["document_metadata_max_output_tokens"] = max_output_tokens

    payload = preprocess_node(state)
    doc_structure = DocStructure.model_validate(payload["doc_structure"])
    metadata = doc_structure.document_metadata
    result = {"document_metadata": metadata.model_dump() if metadata else None}

    if output is not None:
        output.write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        typer.echo(f"已写入: {output}")
        if not json_out:
            return

    if json_out:
        emit_json(result)


__all__ = ["app"]
