"""Retrieval debug commands (BM25/SPLADE)."""

from __future__ import annotations

from pathlib import Path

import typer

from pipelines.graphs.nodes.locators.retrieval_bm25 import bm25_retrieval_locator_node
from pipelines.graphs.nodes.locators.retrieval_splade import splade_retrieval_locator_node
from schemas.internal.evidence import EvidenceCandidate
from .shared import emit_json, load_doc_structure, load_question_set, print_candidates, resolve_splade_model


app = typer.Typer(
    help="检索与召回调试",
    context_settings={"help_option_names": ["-h", "--help"]},
    add_completion=False,
    no_args_is_help=True,
    options_metavar="[选项]",
    subcommand_metavar="命令 [参数]",
)


@app.command("bm25", help="运行 BM25 检索")
def bm25(
    pdf_path: Path = typer.Argument(
        ...,
        exists=True,
        dir_okay=False,
        readable=True,
        metavar="PDF路径",
    ),
    question_id: str | None = typer.Option(
        None,
        "--question-id",
        help="仅输出指定问题（例如 q1_1）",
    ),
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
    full: bool = typer.Option(False, "--full", help="输出全部候选"),
    json_out: bool = typer.Option(False, "--json", help="输出 JSON"),
) -> None:
    doc_structure = load_doc_structure(pdf_path)
    question_set = load_question_set()
    state = {
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
    }
    output = bm25_retrieval_locator_node(state)
    candidates_by_q = output.get("bm25_candidates") or {}

    if json_out:
        emit_json(output)
        return

    if question_id:
        if question_id not in candidates_by_q:
            raise typer.BadParameter(f"Unknown question_id: {question_id}")
        typer.echo(f"\n== {question_id} ==")
        candidates = [EvidenceCandidate.model_validate(item) for item in candidates_by_q[question_id]]
        print_candidates(question_id, candidates, limit=top_k, full=full)
        return

    for qid, raw_items in candidates_by_q.items():
        typer.echo(f"\n== {qid} ==")
        candidates = [EvidenceCandidate.model_validate(item) for item in raw_items]
        print_candidates(qid, candidates, limit=top_k, full=full)


@app.command("splade", help="运行 SPLADE 检索")
def splade(
    pdf_path: Path = typer.Argument(
        ...,
        exists=True,
        dir_okay=False,
        readable=True,
        metavar="PDF路径",
    ),
    question_id: str | None = typer.Option(
        None,
        "--question-id",
        help="仅输出指定问题（例如 q1_1）",
    ),
    model_id: str | None = typer.Option(None, "--model-id", help="SPLADE 模型"),
    device: str | None = typer.Option(None, "--device", help="设备（cpu|cuda|mps）"),
    hf_token: str | None = typer.Option(None, "--hf-token", help="HuggingFace token"),
    doc_max_length: int = typer.Option(256, "--doc-max-length", help="文档最大长度"),
    query_max_length: int = typer.Option(64, "--query-max-length", help="查询最大长度"),
    batch_size: int = typer.Option(8, "--batch-size", help="批大小"),
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
    full: bool = typer.Option(False, "--full", help="输出全部候选"),
    json_out: bool = typer.Option(False, "--json", help="输出 JSON"),
) -> None:
    doc_structure = load_doc_structure(pdf_path)
    question_set = load_question_set()
    state = {
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
        "splade_model_id": resolve_splade_model(model_id),
        "splade_device": device,
        "splade_hf_token": hf_token,
        "splade_doc_max_length": doc_max_length,
        "splade_query_max_length": query_max_length,
        "splade_batch_size": batch_size,
    }
    output = splade_retrieval_locator_node(state)
    candidates_by_q = output.get("splade_candidates") or {}

    if json_out:
        emit_json(output)
        return

    if question_id:
        if question_id not in candidates_by_q:
            raise typer.BadParameter(f"Unknown question_id: {question_id}")
        typer.echo(f"\n== {question_id} ==")
        candidates = [EvidenceCandidate.model_validate(item) for item in candidates_by_q[question_id]]
        print_candidates(question_id, candidates, limit=top_k, full=full)
        return

    for qid, raw_items in candidates_by_q.items():
        typer.echo(f"\n== {qid} ==")
        candidates = [EvidenceCandidate.model_validate(item) for item in raw_items]
        print_candidates(qid, candidates, limit=top_k, full=full)


__all__ = ["app"]
