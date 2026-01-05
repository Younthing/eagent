"""Locator debug commands."""

from __future__ import annotations

from pathlib import Path

import typer

from pipelines.graphs.nodes.locators.rule_based import rule_based_locate
from rob2.locator_rules import DEFAULT_LOCATOR_RULES, load_locator_rules
from .shared import emit_json, load_doc_structure, load_question_set, print_candidates


app = typer.Typer(
    help="证据定位调试",
    context_settings={"help_option_names": ["-h", "--help"]},
    add_completion=False,
    no_args_is_help=True,
    options_metavar="[选项]",
    subcommand_metavar="命令 [参数]",
)


@app.command("rule", help="运行规则定位")
def rule_locator(
    pdf_path: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True),
    question_id: str | None = typer.Option(
        None,
        "--question-id",
        help="仅输出指定问题（例如 q1_1）",
    ),
    top_k: int = typer.Option(5, "--top-k", help="每题输出的候选数量"),
    full: bool = typer.Option(False, "--full", help="输出全部候选"),
    rules_path: Path = typer.Option(
        DEFAULT_LOCATOR_RULES,
        "--rules-path",
        help="locator_rules.yaml 路径",
    ),
    json_out: bool = typer.Option(False, "--json", help="输出 JSON"),
) -> None:
    doc_structure = load_doc_structure(pdf_path)
    question_set = load_question_set()
    rules = load_locator_rules(rules_path)

    candidates_by_q, bundles = rule_based_locate(
        doc_structure,
        question_set,
        rules,
        top_k=top_k,
    )

    if json_out:
        payload = {
            "rule_based_candidates": {
                qid: [candidate.model_dump() for candidate in candidates]
                for qid, candidates in candidates_by_q.items()
            },
            "rule_based_evidence": [bundle.model_dump() for bundle in bundles],
            "rules_version": rules.version,
        }
        emit_json(payload)
        return

    if question_id:
        if question_id not in candidates_by_q:
            raise typer.BadParameter(f"Unknown question_id: {question_id}")
        typer.echo(f"\n== {question_id} ==")
        print_candidates(
            question_id,
            candidates_by_q[question_id],
            limit=top_k,
            full=full,
        )
        return

    for bundle in bundles:
        typer.echo(f"\n== {bundle.question_id} ==")
        print_candidates(
            bundle.question_id,
            candidates_by_q[bundle.question_id],
            limit=top_k,
            full=full,
        )


__all__ = ["app"]
