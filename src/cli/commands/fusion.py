"""Evidence fusion debug commands."""

from __future__ import annotations

from pathlib import Path

import typer

from pipelines.graphs.nodes.fusion import fusion_node
from pipelines.graphs.nodes.locators.retrieval_bm25 import bm25_retrieval_locator_node
from pipelines.graphs.nodes.locators.retrieval_splade import splade_retrieval_locator_node
from pipelines.graphs.nodes.locators.rule_based import rule_based_locator_node
from schemas.internal.evidence import FusedEvidenceCandidate
from .shared import emit_json, load_doc_structure, load_question_set, print_candidates, resolve_splade_model


app = typer.Typer(
    help="证据融合调试",
    context_settings={"help_option_names": ["-h", "--help"]},
    add_completion=False,
    no_args_is_help=True,
    options_metavar="[选项]",
    subcommand_metavar="命令 [参数]",
)


@app.command("run", help="运行融合并输出候选")
def run_fusion(
    pdf_path: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True),
    question_id: str | None = typer.Option(None, "--question-id", help="仅输出指定问题"),
    top_k: int = typer.Option(5, "--top-k", help="输出的候选数量"),
    per_query_top_n: int = typer.Option(50, "--per-query-top-n", help="每个查询保留的候选数"),
    rrf_k: int = typer.Option(60, "--rrf-k", help="RRF 常量"),
    planner: str = typer.Option("deterministic", "--planner", help="查询规划：deterministic|llm"),
    planner_model: str | None = typer.Option(None, "--planner-model", help="规划模型"),
    planner_provider: str | None = typer.Option(None, "--planner-provider", help="规划模型提供方"),
    planner_temperature: float | None = typer.Option(None, "--planner-temperature", help="规划温度"),
    planner_timeout: float | None = typer.Option(None, "--planner-timeout", help="规划超时（秒）"),
    planner_max_tokens: int | None = typer.Option(None, "--planner-max-tokens", help="规划 max_tokens"),
    planner_max_retries: int | None = typer.Option(None, "--planner-max-retries", help="规划重试次数"),
    planner_max_keywords: int | None = typer.Option(None, "--planner-max-keywords", help="规划关键词数量"),
    reranker: str = typer.Option("none", "--reranker", help="重排器：none|cross_encoder"),
    reranker_model_id: str | None = typer.Option(None, "--reranker-model-id", help="重排模型"),
    reranker_device: str | None = typer.Option(None, "--reranker-device", help="重排设备"),
    reranker_max_length: int | None = typer.Option(None, "--reranker-max-length", help="重排 max_length"),
    reranker_batch_size: int | None = typer.Option(None, "--reranker-batch-size", help="重排 batch size"),
    rerank_top_n: int | None = typer.Option(None, "--rerank-top-n", help="重排 top-N"),
    structure: bool = typer.Option(True, "--structure/--no-structure", help="结构感知过滤"),
    section_bonus_weight: float = typer.Option(0.25, "--section-bonus-weight", help="章节加权系数"),
    splade_model_id: str | None = typer.Option(None, "--splade-model-id", help="SPLADE 模型"),
    splade_device: str | None = typer.Option(None, "--splade-device", help="SPLADE 设备"),
    splade_hf_token: str | None = typer.Option(None, "--splade-hf-token", help="SPLADE HF token"),
    splade_doc_max_length: int = typer.Option(256, "--splade-doc-max-length", help="SPLADE 文档长度"),
    splade_query_max_length: int = typer.Option(64, "--splade-query-max-length", help="SPLADE 查询长度"),
    splade_batch_size: int = typer.Option(8, "--splade-batch-size", help="SPLADE batch size"),
    full: bool = typer.Option(False, "--full", help="输出全部候选"),
    json_out: bool = typer.Option(False, "--json", help="输出 JSON"),
) -> None:
    doc_structure = load_doc_structure(pdf_path)
    question_set = load_question_set()
    base_state = {
        "doc_structure": doc_structure.model_dump(),
        "question_set": question_set.model_dump(),
        "top_k": top_k,
        "per_query_top_n": per_query_top_n,
        "rrf_k": rrf_k,
        "query_planner": planner,
        "query_planner_model": planner_model,
        "query_planner_model_provider": planner_provider,
        "query_planner_temperature": planner_temperature,
        "query_planner_timeout": planner_timeout,
        "query_planner_max_tokens": planner_max_tokens,
        "query_planner_max_retries": planner_max_retries,
        "query_planner_max_keywords": planner_max_keywords,
        "reranker": reranker,
        "reranker_model_id": reranker_model_id,
        "reranker_device": reranker_device,
        "reranker_max_length": reranker_max_length,
        "reranker_batch_size": reranker_batch_size,
        "rerank_top_n": rerank_top_n,
        "use_structure": structure,
        "section_bonus_weight": section_bonus_weight,
        "splade_model_id": resolve_splade_model(splade_model_id),
        "splade_device": splade_device,
        "splade_hf_token": splade_hf_token,
        "splade_doc_max_length": splade_doc_max_length,
        "splade_query_max_length": splade_query_max_length,
        "splade_batch_size": splade_batch_size,
        "fusion_top_k": top_k,
        "fusion_rrf_k": rrf_k,
    }

    rule_based = rule_based_locator_node(base_state)
    bm25 = bm25_retrieval_locator_node(base_state)
    splade = splade_retrieval_locator_node(base_state)
    fusion = fusion_node({**base_state, **rule_based, **bm25, **splade})

    if json_out:
        emit_json({**base_state, **rule_based, **bm25, **splade, **fusion})
        return

    candidates_by_q = fusion.get("fusion_candidates") or {}
    if question_id:
        if question_id not in candidates_by_q:
            raise typer.BadParameter(f"Unknown question_id: {question_id}")
        typer.echo(f"\n== {question_id} ==")
        candidates = [FusedEvidenceCandidate.model_validate(item) for item in candidates_by_q[question_id]]
        print_candidates(question_id, candidates, limit=top_k, full=full)
        return

    for qid, raw_items in candidates_by_q.items():
        typer.echo(f"\n== {qid} ==")
        candidates = [FusedEvidenceCandidate.model_validate(item) for item in raw_items]
        print_candidates(qid, candidates, limit=top_k, full=full)


__all__ = ["app"]
