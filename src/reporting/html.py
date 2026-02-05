"""HTML report renderer for ROB2."""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from reporting.context import build_report_context
from schemas.responses import Rob2RunResult


def render_html(result: Rob2RunResult, *, pdf_name: str) -> str:
    template_dir = Path(__file__).parent / "templates"
    env = Environment(loader=FileSystemLoader(str(template_dir)))
    template = env.get_template("report.html")
    context = build_report_context(result, pdf_name=pdf_name)
    return template.render(**context)


def generate_html_report(result: Rob2RunResult, output_path: Path, pdf_name: str = "Unknown") -> None:
    """Generate interactive HTML report."""
    output_path.write_text(render_html(result, pdf_name=pdf_name), encoding="utf-8")


__all__ = ["generate_html_report", "render_html"]
