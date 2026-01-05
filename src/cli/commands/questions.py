"""Question bank commands."""

from __future__ import annotations

from pathlib import Path

import typer

from rob2.question_bank import DEFAULT_QUESTION_BANK, load_question_bank
from schemas.internal.rob2 import QuestionSet
from .shared import emit_json


app = typer.Typer(
    help="题库查看与导出",
    context_settings={"help_option_names": ["-h", "--help"]},
    add_completion=False,
    no_args_is_help=True,
    options_metavar="[选项]",
    subcommand_metavar="命令 [参数]",
)


@app.command("list", help="查看题库概要")
def list_questions(
    path: Path = typer.Option(
        DEFAULT_QUESTION_BANK,
        "--path",
        help="题库 YAML 路径",
    ),
    json_out: bool = typer.Option(False, "--json", help="输出完整 JSON"),
) -> None:
    question_set = load_question_bank(path)
    if json_out:
        emit_json(question_set.model_dump())
        return

    _print_summary(question_set, path)


@app.command("export", help="导出题库为 JSON")
def export_questions(
    output: Path | None = typer.Option(
        None,
        "--output",
        help="导出的 JSON 文件路径（默认输出到 stdout）",
    ),
    path: Path = typer.Option(
        DEFAULT_QUESTION_BANK,
        "--path",
        help="题库 YAML 路径",
    ),
) -> None:
    question_set = load_question_bank(path)
    payload = question_set.model_dump()
    if output is None:
        emit_json(payload)
        return
    output.write_text(
        json_dumps(payload),
        encoding="utf-8",
    )
    typer.echo(f"已写入: {output}")


def _print_summary(question_set: QuestionSet, path: Path) -> None:
    assignment = [
        question
        for question in question_set.questions
        if question.domain == "D2" and question.effect_type == "assignment"
    ]
    adherence = [
        question
        for question in question_set.questions
        if question.domain == "D2" and question.effect_type == "adherence"
    ]
    typer.echo(f"Question bank: {path}")
    typer.echo(f"Version: {question_set.version}")
    typer.echo(f"Variant: {question_set.variant}")
    typer.echo(f"Total questions: {len(question_set.questions)}")
    typer.echo(f"D2 assignment questions: {len(assignment)}")
    typer.echo(f"D2 adherence questions: {len(adherence)}")
    typer.echo("First/last question_id:")
    typer.echo(f"  first: {question_set.questions[0].question_id}")
    typer.echo(f"  last:  {question_set.questions[-1].question_id}")


def json_dumps(payload: object) -> str:
    import json

    return json.dumps(payload, ensure_ascii=False, indent=2)


__all__ = ["app"]
