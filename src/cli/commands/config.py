"""Configuration inspection commands."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import typer

from core.config import Settings, get_settings
from schemas.requests import Rob2RunOptions
from .shared import emit_json


app = typer.Typer(
    help="配置查看与导出",
    context_settings={"help_option_names": ["-h", "--help"]},
    add_completion=False,
    no_args_is_help=True,
    options_metavar="[选项]",
    subcommand_metavar="命令 [参数]",
)


@app.command("show", help="查看当前生效配置")
def show_config(
    json_out: bool = typer.Option(True, "--json/--no-json", help="输出 JSON"),
) -> None:
    settings = get_settings()
    payload = settings.model_dump()
    if json_out:
        emit_json(payload)
        return
    for key, value in payload.items():
        typer.echo(f"{key}={value}")


@app.command("export", help="导出配置为 JSON")
def export_config(
    output: Path | None = typer.Option(
        None,
        "--output",
        help="导出的 JSON 文件路径（默认输出到 stdout）",
    ),
) -> None:
    payload = get_settings().model_dump()
    if output is None:
        emit_json(payload)
        return
    output.write_text(json_dumps(payload), encoding="utf-8")
    typer.echo(f"已写入: {output}")


@app.command("diff", help="显示与默认值的差异")
def diff_config() -> None:
    settings = get_settings()
    defaults = _settings_defaults()
    current = settings.model_dump()
    diff: dict[str, dict[str, Any]] = {}
    for key, value in current.items():
        default = defaults.get(key)
        if value != default:
            diff[key] = {"value": value, "default": default}
    emit_json(diff)


@app.command("options", help="查看可设置的运行参数")
def list_run_options(
    json_out: bool = typer.Option(False, "--json", help="输出 JSON"),
    schema: bool = typer.Option(False, "--schema", help="输出 Pydantic schema"),
) -> None:
    if schema:
        emit_json(Rob2RunOptions.model_json_schema())
        return
    catalog = _options_catalog()
    if json_out:
        emit_json(catalog)
        return

    for group in catalog:
        typer.echo(f"\n[{group['group']}]")
        for item in group["items"]:
            desc = item.get("desc") or ""
            choices = item.get("choices")
            hint = f"  可选: {' | '.join(choices)}" if choices else ""
            typer.echo(f"- {item['key']}: {desc}{hint}")


@app.command("example", help="生成示例配置 YAML")
def write_example_config(
    output: Path = typer.Option(
        Path.cwd() / "rob2.options.yaml",
        "--output",
        help="输出文件路径（默认写入当前目录）",
    ),
    force: bool = typer.Option(False, "--force", help="覆盖已存在文件"),
) -> None:
    if output.exists() and not force:
        raise typer.BadParameter(f"文件已存在，请使用 --force 覆盖: {output}")
    content = _render_example_yaml()
    output.write_text(content, encoding="utf-8")
    typer.echo(f"已写入: {output}")


def _settings_defaults() -> dict[str, Any]:
    defaults: dict[str, Any] = {}
    for name, field in Settings.model_fields.items():
        defaults[name] = field.default
    return defaults


def json_dumps(payload: object) -> str:
    import json

    return json.dumps(payload, ensure_ascii=False, indent=2)


def _options_catalog() -> list[dict[str, Any]]:
    return [
        {
            "group": "预处理（Docling）",
            "items": [
                {
                    "key": "docling_layout_model",
                    "desc": "Docling 布局模型 ID 或本地路径",
                },
                {
                    "key": "docling_artifacts_path",
                    "desc": "Docling 产物缓存目录",
                },
                {
                    "key": "docling_chunker_model",
                    "desc": "Docling chunker 模型",
                },
                {
                    "key": "docling_chunker_max_tokens",
                    "desc": "Chunker 最大 token 数",
                },
                {
                    "key": "preprocess_drop_references",
                    "desc": "预处理过滤参考文献",
                },
                {
                    "key": "preprocess_reference_titles",
                    "desc": "参考文献标题匹配列表",
                },
                {
                    "key": "doc_scope_mode",
                    "desc": "Doc Scope 模式",
                    "choices": ["auto", "manual", "none"],
                },
                {
                    "key": "doc_scope_include_paragraph_ids",
                    "desc": "手动段落选择（paragraph_id 列表）",
                },
                {
                    "key": "doc_scope_page_range",
                    "desc": "手动页码范围（例如 1-3,5）",
                },
                {
                    "key": "doc_scope_min_pages",
                    "desc": "自动裁剪最小页数",
                },
                {
                    "key": "doc_scope_min_confidence",
                    "desc": "自动裁剪最小置信度",
                },
                {
                    "key": "doc_scope_abstract_gap_pages",
                    "desc": "双语摘要起点间隔阈值",
                },
            ],
        },
        {
            "group": "检索与融合",
            "items": [
                {"key": "top_k", "desc": "每题保留候选数量"},
                {"key": "per_query_top_n", "desc": "每个查询保留候选数"},
                {"key": "rrf_k", "desc": "RRF 融合常量"},
                {
                    "key": "query_planner",
                    "desc": "查询规划策略",
                    "choices": ["deterministic", "llm"],
                },
                {"key": "query_planner_model", "desc": "规划模型 ID"},
                {"key": "query_planner_model_provider", "desc": "规划模型提供方"},
                {"key": "query_planner_temperature", "desc": "规划温度"},
                {"key": "query_planner_timeout", "desc": "规划超时（秒）"},
                {"key": "query_planner_max_tokens", "desc": "规划 max_tokens"},
                {"key": "query_planner_max_retries", "desc": "规划重试次数"},
                {"key": "query_planner_max_keywords", "desc": "规划关键词数量"},
                {
                    "key": "reranker",
                    "desc": "重排策略",
                    "choices": ["none", "cross_encoder"],
                },
                {"key": "reranker_model_id", "desc": "重排模型 ID"},
                {"key": "reranker_device", "desc": "重排设备（cpu|cuda|mps）"},
                {"key": "reranker_max_length", "desc": "重排 max_length"},
                {"key": "reranker_batch_size", "desc": "重排 batch size"},
                {"key": "rerank_top_n", "desc": "重排 top-N"},
                {"key": "use_structure", "desc": "启用结构感知过滤"},
                {"key": "section_bonus_weight", "desc": "章节加权系数"},
                {"key": "locator_tokenizer", "desc": "定位分词器策略"},
                {"key": "locator_char_ngram", "desc": "中文 n-gram 长度"},
                {"key": "splade_model_id", "desc": "SPLADE 模型 ID"},
                {"key": "splade_device", "desc": "SPLADE 设备"},
                {"key": "splade_hf_token", "desc": "HuggingFace token"},
                {"key": "splade_query_max_length", "desc": "SPLADE 查询最大长度"},
                {"key": "splade_doc_max_length", "desc": "SPLADE 文档最大长度"},
                {"key": "splade_batch_size", "desc": "SPLADE batch size"},
                {"key": "fusion_top_k", "desc": "融合后保留 top_k"},
                {"key": "fusion_rrf_k", "desc": "融合 RRF 常量"},
                {"key": "fusion_engine_weights", "desc": "融合引擎权重映射"},
            ],
        },
        {
            "group": "验证（Evidence Validation）",
            "items": [
                {
                    "key": "relevance_mode",
                    "desc": "相关性验证模式",
                    "choices": ["none", "llm"],
                },
                {"key": "relevance_model", "desc": "相关性模型 ID"},
                {"key": "relevance_model_provider", "desc": "相关性模型提供方"},
                {"key": "relevance_temperature", "desc": "相关性温度"},
                {"key": "relevance_timeout", "desc": "相关性超时（秒）"},
                {"key": "relevance_max_tokens", "desc": "相关性 max_tokens"},
                {"key": "relevance_max_retries", "desc": "相关性重试次数"},
                {"key": "relevance_min_confidence", "desc": "相关性最小置信度"},
                {"key": "relevance_require_quote", "desc": "相关性需引用原文"},
                {"key": "relevance_fill_to_top_k", "desc": "相关性不足时回填"},
                {"key": "relevance_top_k", "desc": "相关性保留 top_k"},
                {"key": "relevance_top_n", "desc": "相关性验证 top_n"},
                {"key": "existence_require_text_match", "desc": "存在性需文本匹配"},
                {"key": "existence_require_quote_in_source", "desc": "引用需在原文"},
                {"key": "existence_top_k", "desc": "存在性保留 top_k"},
                {
                    "key": "consistency_mode",
                    "desc": "一致性验证模式",
                    "choices": ["none", "llm"],
                },
                {"key": "consistency_model", "desc": "一致性模型 ID"},
                {"key": "consistency_model_provider", "desc": "一致性模型提供方"},
                {"key": "consistency_temperature", "desc": "一致性温度"},
                {"key": "consistency_timeout", "desc": "一致性超时（秒）"},
                {"key": "consistency_max_tokens", "desc": "一致性 max_tokens"},
                {"key": "consistency_max_retries", "desc": "一致性重试次数"},
                {"key": "consistency_min_confidence", "desc": "一致性最小置信度"},
                {"key": "consistency_require_quotes_for_fail", "desc": "一致性失败需引用"},
                {"key": "consistency_top_n", "desc": "一致性验证 top_n"},
                {"key": "completeness_enforce", "desc": "完整性强制失败"},
                {"key": "completeness_required_questions", "desc": "完整性必答问题列表"},
                {"key": "completeness_min_passed_per_question", "desc": "每题最小通过数"},
                {"key": "completeness_require_relevance", "desc": "完整性是否依赖相关性"},
                {"key": "validated_top_k", "desc": "最终候选 top_k"},
                {"key": "validation_max_retries", "desc": "验证层重试次数"},
                {"key": "validation_fail_on_consistency", "desc": "一致性失败直接失败"},
                {"key": "validation_relax_on_retry", "desc": "重试时放宽阈值"},
            ],
        },
        {
            "group": "领域推理（D1-D5）",
            "items": [
                {
                    "key": "d2_effect_type",
                    "desc": "D2 效应类型",
                    "choices": ["assignment", "adherence"],
                },
                {"key": "domain_evidence_top_k", "desc": "领域证据 top_k"},
                {"key": "d1_model", "desc": "D1 模型 ID"},
                {"key": "d1_model_provider", "desc": "D1 模型提供方"},
                {"key": "d1_temperature", "desc": "D1 温度"},
                {"key": "d1_timeout", "desc": "D1 超时（秒）"},
                {"key": "d1_max_tokens", "desc": "D1 max_tokens"},
                {"key": "d1_max_retries", "desc": "D1 重试次数"},
                {"key": "d2_model", "desc": "D2 模型 ID"},
                {"key": "d2_model_provider", "desc": "D2 模型提供方"},
                {"key": "d2_temperature", "desc": "D2 温度"},
                {"key": "d2_timeout", "desc": "D2 超时（秒）"},
                {"key": "d2_max_tokens", "desc": "D2 max_tokens"},
                {"key": "d2_max_retries", "desc": "D2 重试次数"},
                {"key": "d3_model", "desc": "D3 模型 ID"},
                {"key": "d3_model_provider", "desc": "D3 模型提供方"},
                {"key": "d3_temperature", "desc": "D3 温度"},
                {"key": "d3_timeout", "desc": "D3 超时（秒）"},
                {"key": "d3_max_tokens", "desc": "D3 max_tokens"},
                {"key": "d3_max_retries", "desc": "D3 重试次数"},
                {"key": "d4_model", "desc": "D4 模型 ID"},
                {"key": "d4_model_provider", "desc": "D4 模型提供方"},
                {"key": "d4_temperature", "desc": "D4 温度"},
                {"key": "d4_timeout", "desc": "D4 超时（秒）"},
                {"key": "d4_max_tokens", "desc": "D4 max_tokens"},
                {"key": "d4_max_retries", "desc": "D4 重试次数"},
                {"key": "d5_model", "desc": "D5 模型 ID"},
                {"key": "d5_model_provider", "desc": "D5 模型提供方"},
                {"key": "d5_temperature", "desc": "D5 温度"},
                {"key": "d5_timeout", "desc": "D5 超时（秒）"},
                {"key": "d5_max_tokens", "desc": "D5 max_tokens"},
                {"key": "d5_max_retries", "desc": "D5 重试次数"},
            ],
        },
        {
            "group": "领域审计（Domain Audit）",
            "items": [
                {
                    "key": "domain_audit_mode",
                    "desc": "审计模式",
                    "choices": ["none", "llm"],
                },
                {"key": "domain_audit_model", "desc": "审计模型 ID"},
                {"key": "domain_audit_model_provider", "desc": "审计模型提供方"},
                {"key": "domain_audit_temperature", "desc": "审计温度"},
                {"key": "domain_audit_timeout", "desc": "审计超时（秒）"},
                {"key": "domain_audit_max_tokens", "desc": "审计 max_tokens"},
                {"key": "domain_audit_max_retries", "desc": "审计重试次数"},
                {"key": "domain_audit_patch_window", "desc": "证据补丁窗口"},
                {
                    "key": "domain_audit_max_patches_per_question",
                    "desc": "每题最大补丁数",
                },
                {"key": "domain_audit_rerun_domains", "desc": "审计后重跑领域"},
                {"key": "domain_audit_final", "desc": "最终全域审计"},
            ],
        },
        {
            "group": "输出控制",
            "items": [
                {
                    "key": "debug_level",
                    "desc": "调试级别",
                    "choices": ["none", "min", "full"],
                },
                {"key": "include_reports", "desc": "输出验证报告"},
                {"key": "include_audit_reports", "desc": "输出审计报告"},
            ],
        },
    ]


def _render_example_yaml() -> str:
    def _format_value(value: Any) -> str:
        if value is None:
            return "null"
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, (int, float)):
            return str(value)
        if isinstance(value, list):
            return "[]"
        if isinstance(value, dict):
            return "{}"
        text = str(value).replace("'", "''")
        return f"'{text}'"

    examples: dict[str, Any] = {
        "doc_scope_mode": "auto",
        "query_planner": "deterministic",
        "reranker": "none",
        "use_structure": True,
        "relevance_mode": "none",
        "consistency_mode": "none",
        "d2_effect_type": "assignment",
        "domain_audit_mode": "none",
        "debug_level": "none",
    }

    lines: list[str] = []
    lines.append("# ROB2 运行参数示例（仅填写需要覆盖的字段）")
    lines.append("# 规则：CLI/API 参数 > 配置文件 > 环境变量/.env")
    lines.append("# 将 null 保持为未设置即可")

    for group in _options_catalog():
        lines.append("")
        lines.append(f"# --- {group['group']} ---")
        for item in group["items"]:
            desc = item.get("desc") or ""
            choices = item.get("choices")
            key = item["key"]
            lines.append(f"# {desc}")
            if choices:
                lines.append(f"# 可选值: {' | '.join(choices)}")
            value = examples.get(key)
            lines.append(f"{key}: {_format_value(value)}")

    return "\n".join(lines) + "\n"


__all__ = ["app"]
