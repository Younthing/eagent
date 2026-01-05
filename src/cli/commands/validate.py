"""Validation debug commands."""

from __future__ import annotations

from pathlib import Path

import typer

from pipelines.graphs.nodes.fusion import fusion_node
from pipelines.graphs.nodes.locators.retrieval_bm25 import bm25_retrieval_locator_node
from pipelines.graphs.nodes.locators.retrieval_splade import splade_retrieval_locator_node
from pipelines.graphs.nodes.locators.rule_based import rule_based_locator_node
from pipelines.graphs.nodes.validators.completeness import completeness_validator_node
from pipelines.graphs.nodes.validators.consistency import consistency_validator_node
from pipelines.graphs.nodes.validators.existence import existence_validator_node
from pipelines.graphs.nodes.validators.relevance import relevance_validator_node
from schemas.internal.evidence import FusedEvidenceCandidate
from .shared import emit_json, load_doc_structure, load_question_set, print_candidates, resolve_splade_model


app = typer.Typer(
    help="验证层调试",
    context_settings={"help_option_names": ["-h", "--help"]},
    add_completion=False,
    no_args_is_help=True,
    options_metavar="[选项]",
    subcommand_metavar="命令 [参数]",
)


def _base_state(
    pdf_path: Path,
    *,
    top_k: int,
    per_query_top_n: int,
    rrf_k: int,
    planner: str,
    planner_model: str | None,
    planner_provider: str | None,
    planner_temperature: float | None,
    planner_timeout: float | None,
    planner_max_tokens: int | None,
    planner_max_retries: int | None,
    planner_max_keywords: int | None,
    reranker: str,
    reranker_model_id: str | None,
    reranker_device: str | None,
    reranker_max_length: int | None,
    reranker_batch_size: int | None,
    rerank_top_n: int | None,
    structure: bool,
    section_bonus_weight: float,
    splade_model_id: str | None,
    splade_device: str | None,
    splade_hf_token: str | None,
    splade_doc_max_length: int,
    splade_query_max_length: int,
    splade_batch_size: int,
) -> dict:
    doc_structure = load_doc_structure(pdf_path)
    question_set = load_question_set()
    return {
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


def _run_locators(state: dict) -> dict:
    rule_based = rule_based_locator_node(state)
    bm25 = bm25_retrieval_locator_node(state)
    splade = splade_retrieval_locator_node(state)
    fusion = fusion_node({**state, **rule_based, **bm25, **splade})
    return {**state, **rule_based, **bm25, **splade, **fusion}


@app.command("full", help="运行完整验证链路")
def validate_full(
    pdf_path: Path = typer.Argument(
        ...,
        exists=True,
        dir_okay=False,
        readable=True,
        metavar="PDF路径",
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
    splade_model_id: str | None = typer.Option(None, "--splade-model-id", help="SPLADE 模型"),
    splade_device: str | None = typer.Option(None, "--splade-device", help="SPLADE 设备"),
    splade_hf_token: str | None = typer.Option(None, "--splade-hf-token", help="SPLADE HF token"),
    splade_doc_max_length: int = typer.Option(256, "--splade-doc-max-length", help="SPLADE 文档长度"),
    splade_query_max_length: int = typer.Option(64, "--splade-query-max-length", help="SPLADE 查询长度"),
    splade_batch_size: int = typer.Option(8, "--splade-batch-size", help="SPLADE batch size"),
    relevance: str = typer.Option("none", "--relevance", help="相关性：none|llm"),
    consistency: str = typer.Option("none", "--consistency", help="一致性：none|llm"),
    min_confidence: float = typer.Option(0.6, "--min-confidence", help="最小置信度"),
    require_quote: bool = typer.Option(True, "--require-quote/--no-require-quote", help="要求引用"),
    existence_require_text_match: bool = typer.Option(
        True,
        "--existence-require-text-match/--no-existence-require-text-match",
        help="要求文本匹配",
    ),
    existence_require_quote_in_source: bool = typer.Option(
        True,
        "--existence-require-quote-in-source/--no-existence-require-quote-in-source",
        help="要求引用在原文",
    ),
    enforce_completeness: bool = typer.Option(False, "--enforce-completeness", help="严格完整性"),
    json_out: bool = typer.Option(False, "--json", help="输出 JSON"),
) -> None:
    base_state = _base_state(
        pdf_path,
        top_k=top_k,
        per_query_top_n=per_query_top_n,
        rrf_k=rrf_k,
        planner=planner,
        planner_model=planner_model,
        planner_provider=planner_provider,
        planner_temperature=planner_temperature,
        planner_timeout=planner_timeout,
        planner_max_tokens=planner_max_tokens,
        planner_max_retries=planner_max_retries,
        planner_max_keywords=planner_max_keywords,
        reranker=reranker,
        reranker_model_id=reranker_model_id,
        reranker_device=reranker_device,
        reranker_max_length=reranker_max_length,
        reranker_batch_size=reranker_batch_size,
        rerank_top_n=rerank_top_n,
        structure=structure,
        section_bonus_weight=section_bonus_weight,
        splade_model_id=splade_model_id,
        splade_device=splade_device,
        splade_hf_token=splade_hf_token,
        splade_doc_max_length=splade_doc_max_length,
        splade_query_max_length=splade_query_max_length,
        splade_batch_size=splade_batch_size,
    )
    state = _run_locators(base_state)
    state.update(
        {
            "relevance_mode": relevance,
            "relevance_min_confidence": min_confidence,
            "relevance_require_quote": require_quote,
            "relevance_top_k": top_k,
        }
    )
    relevance_out = relevance_validator_node(state)
    state = {**state, **relevance_out}
    state.update(
        {
            "existence_top_k": top_k,
            "existence_require_text_match": existence_require_text_match,
            "existence_require_quote_in_source": existence_require_quote_in_source,
        }
    )
    existence_out = existence_validator_node(state)
    state = {**state, **existence_out}
    state.update(
        {
            "consistency_mode": consistency,
            "consistency_min_confidence": min_confidence,
        }
    )
    consistency_out = consistency_validator_node(state)
    state = {**state, **consistency_out}
    state.update({"validated_top_k": top_k, "completeness_enforce": enforce_completeness})
    completeness_out = completeness_validator_node(state)
    state = {**state, **completeness_out}

    if json_out:
        emit_json(state)
        return

    passed = state.get("completeness_passed")
    failed = state.get("completeness_failed_questions") or []
    consistency_failed = state.get("consistency_failed_questions") or []
    typer.echo(f"completeness_passed={passed}")
    typer.echo(f"failed_questions={len(failed)} consistency_failed={len(consistency_failed)}")
    if failed:
        typer.echo(f"failed: {', '.join(failed)}")


@app.command("relevance", help="运行相关性验证")
def validate_relevance(
    pdf_path: Path = typer.Argument(
        ...,
        exists=True,
        dir_okay=False,
        readable=True,
        metavar="PDF路径",
    ),
    question_id: str | None = typer.Option(None, "--question-id", help="仅输出指定问题"),
    top_k: int = typer.Option(5, "--top-k", help="输出的候选数量"),
    per_query_top_n: int = typer.Option(50, "--per-query-top-n", help="每个查询保留的候选数"),
    rrf_k: int = typer.Option(60, "--rrf-k", help="RRF 常量"),
    relevance: str = typer.Option("none", "--relevance", help="相关性：none|llm"),
    min_confidence: float = typer.Option(0.6, "--min-confidence", help="最小置信度"),
    require_quote: bool = typer.Option(True, "--require-quote/--no-require-quote", help="要求引用"),
    json_out: bool = typer.Option(False, "--json", help="输出 JSON"),
) -> None:
    base_state = _base_state(
        pdf_path,
        top_k=top_k,
        per_query_top_n=per_query_top_n,
        rrf_k=rrf_k,
        planner="deterministic",
        planner_model=None,
        planner_provider=None,
        planner_temperature=None,
        planner_timeout=None,
        planner_max_tokens=None,
        planner_max_retries=None,
        planner_max_keywords=None,
        reranker="none",
        reranker_model_id=None,
        reranker_device=None,
        reranker_max_length=None,
        reranker_batch_size=None,
        rerank_top_n=None,
        structure=True,
        section_bonus_weight=0.25,
        splade_model_id=None,
        splade_device=None,
        splade_hf_token=None,
        splade_doc_max_length=256,
        splade_query_max_length=64,
        splade_batch_size=8,
    )
    state = _run_locators(base_state)
    state.update(
        {
            "relevance_mode": relevance,
            "relevance_min_confidence": min_confidence,
            "relevance_require_quote": require_quote,
            "relevance_top_k": top_k,
        }
    )
    relevance_out = relevance_validator_node(state)
    if json_out:
        emit_json({**state, **relevance_out})
        return

    candidates_by_q = relevance_out.get("relevance_candidates") or {}
    if question_id:
        if question_id not in candidates_by_q:
            raise typer.BadParameter(f"Unknown question_id: {question_id}")
        typer.echo(f"\n== {question_id} ==")
        candidates = [FusedEvidenceCandidate.model_validate(item) for item in candidates_by_q[question_id]]
        print_candidates(question_id, candidates, limit=top_k, full=False)
        return

    for qid, raw_items in candidates_by_q.items():
        typer.echo(f"\n== {qid} ==")
        candidates = [FusedEvidenceCandidate.model_validate(item) for item in raw_items]
        print_candidates(qid, candidates, limit=top_k, full=False)


@app.command("consistency", help="运行一致性验证")
def validate_consistency(
    pdf_path: Path = typer.Argument(
        ...,
        exists=True,
        dir_okay=False,
        readable=True,
        metavar="PDF路径",
    ),
    min_confidence: float = typer.Option(0.6, "--min-confidence", help="最小置信度"),
    require_quotes_for_fail: bool = typer.Option(
        True,
        "--require-quotes-for-fail/--no-require-quotes-for-fail",
        help="失败必须引用",
    ),
    json_out: bool = typer.Option(False, "--json", help="输出 JSON"),
) -> None:
    base_state = _base_state(
        pdf_path,
        top_k=5,
        per_query_top_n=50,
        rrf_k=60,
        planner="deterministic",
        planner_model=None,
        planner_provider=None,
        planner_temperature=None,
        planner_timeout=None,
        planner_max_tokens=None,
        planner_max_retries=None,
        planner_max_keywords=None,
        reranker="none",
        reranker_model_id=None,
        reranker_device=None,
        reranker_max_length=None,
        reranker_batch_size=None,
        rerank_top_n=None,
        structure=True,
        section_bonus_weight=0.25,
        splade_model_id=None,
        splade_device=None,
        splade_hf_token=None,
        splade_doc_max_length=256,
        splade_query_max_length=64,
        splade_batch_size=8,
    )
    state = _run_locators(base_state)
    relevance_out = relevance_validator_node(
        {
            **state,
            "relevance_mode": "none",
            "relevance_min_confidence": min_confidence,
            "relevance_top_k": 5,
        }
    )
    existence_out = existence_validator_node({**state, **relevance_out})
    consistency_out = consistency_validator_node(
        {
            **state,
            **relevance_out,
            **existence_out,
            "consistency_mode": "llm",
            "consistency_min_confidence": min_confidence,
            "consistency_require_quotes_for_fail": require_quotes_for_fail,
        }
    )
    if json_out:
        emit_json({**state, **relevance_out, **existence_out, **consistency_out})
        return

    failed = consistency_out.get("consistency_failed_questions") or []
    typer.echo(f"consistency_failed_questions={len(failed)}")
    if failed:
        typer.echo(f"failed: {', '.join(failed)}")


@app.command("completeness", help="运行完整性验证")
def validate_completeness(
    pdf_path: Path = typer.Argument(
        ...,
        exists=True,
        dir_okay=False,
        readable=True,
        metavar="PDF路径",
    ),
    enforce: bool = typer.Option(False, "--enforce", help="严格完整性"),
    json_out: bool = typer.Option(False, "--json", help="输出 JSON"),
) -> None:
    base_state = _base_state(
        pdf_path,
        top_k=5,
        per_query_top_n=50,
        rrf_k=60,
        planner="deterministic",
        planner_model=None,
        planner_provider=None,
        planner_temperature=None,
        planner_timeout=None,
        planner_max_tokens=None,
        planner_max_retries=None,
        planner_max_keywords=None,
        reranker="none",
        reranker_model_id=None,
        reranker_device=None,
        reranker_max_length=None,
        reranker_batch_size=None,
        rerank_top_n=None,
        structure=True,
        section_bonus_weight=0.25,
        splade_model_id=None,
        splade_device=None,
        splade_hf_token=None,
        splade_doc_max_length=256,
        splade_query_max_length=64,
        splade_batch_size=8,
    )
    state = _run_locators(base_state)
    relevance_out = relevance_validator_node(
        {
            **state,
            "relevance_mode": "none",
            "relevance_top_k": 5,
        }
    )
    existence_out = existence_validator_node({**state, **relevance_out})
    completeness_out = completeness_validator_node(
        {
            **state,
            **relevance_out,
            **existence_out,
            "validated_top_k": 5,
            "completeness_enforce": enforce,
        }
    )
    if json_out:
        emit_json({**state, **relevance_out, **existence_out, **completeness_out})
        return
    typer.echo(f"completeness_passed={completeness_out.get('completeness_passed')}")
    failed = completeness_out.get("completeness_failed_questions") or []
    typer.echo(f"failed_questions={len(failed)}")
    if failed:
        typer.echo(f"failed: {', '.join(failed)}")


__all__ = ["app"]
