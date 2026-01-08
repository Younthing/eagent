"""Report generation command for ROB2."""

import json
from pathlib import Path

import typer

from schemas.responses import Rob2RunResult

app = typer.Typer(
    help="生成或重新生成 ROB2 评估报告",
    context_settings={"help_option_names": ["-h", "--help"]},
)


@app.command(name="generate", help="从 result.json 生成报告")
def generate(
    result_file: Path = typer.Argument(
        ...,
        exists=True,
        dir_okay=False,
        readable=True,
        metavar="RESULT_JSON",
        help="result.json 文件路径",
    ),
    output_dir: Path = typer.Option(
        ".",
        "--output-dir",
        help="报告输出目录",
    ),
    formats: str = typer.Option(
        "all",
        "--formats",
        help="报告格式,逗号分隔:html,pdf,docx 或 all",
    ),
    title: str | None = typer.Option(
        None,
        "--title",
        help="自定义报告标题",
    ),
    template: str = typer.Option(
        "default",
        "--template",
        help="报告模板名称",
    ),
    no_evidence_text: bool = typer.Option(
        False,
        "--no-evidence-text",
        help="不包含完整证据文本(精简版)",
    ),
    no_confidence_scores: bool = typer.Option(
        False,
        "--no-confidence-scores",
        help="不包含置信度分数",
    ),
    include_validation: bool = typer.Option(
        False,
        "--include-validation",
        help="在报告中包含验证报告",
    ),
    include_audit: bool = typer.Option(
        False,
        "--include-audit",
        help="在报告中包含审核报告",
    ),
) -> None:
    """从已有的 result.json 生成报告文件."""
    # Load result.json
    try:
        result_data = json.loads(result_file.read_text(encoding="utf-8"))
        result = Rob2RunResult.model_validate(result_data)
    except Exception as e:
        typer.echo(f"✗ 加载 result.json 失败: {e}", err=True)
        raise typer.Exit(1)

    # Parse formats
    if formats.lower() == "all":
        format_list = ["html", "pdf", "docx"]
    else:
        format_list = [fmt.strip() for fmt in formats.split(",") if fmt.strip()]

    # Generate reports
    try:
        from reporting.generator import ReportGenerator
        from reporting.schemas import ReportOptions

        report_options = ReportOptions(
            output_dir=output_dir,
            output_formats=format_list,
            report_title=title or "ROB2 Risk of Bias Assessment Report",
            include_evidence_text=not no_evidence_text,
            include_confidence_scores=not no_confidence_scores,
            include_validation_reports=include_validation,
            include_audit_reports=include_audit,
            template_name=template,
        )

        generator = ReportGenerator(report_options)
        report_bundle = generator.generate(
            result.result,
            table_markdown=result.table_markdown,
            validation_reports=result.reports if include_validation else None,
            audit_reports=result.audit_reports if include_audit else None,
        )

        # Display results
        typer.echo("\n✔ 报告生成成功:")
        if report_bundle.html_path:
            typer.echo(f"  - HTML: {report_bundle.html_path}")
        if report_bundle.docx_path:
            typer.echo(f"  - DOCX: {report_bundle.docx_path}")
        if report_bundle.pdf_path:
            typer.echo(f"  - PDF:  {report_bundle.pdf_path}")

        if report_bundle.format_errors:
            typer.echo("\n⚠ 部分格式生成失败:")
            for fmt, error in report_bundle.format_errors.items():
                typer.echo(f"  - {fmt}: {error}")
            raise typer.Exit(1)

    except Exception as e:
        typer.echo(f"✗ 报告生成失败: {e}", err=True)
        raise typer.Exit(1)


__all__ = ["app"]
