"""Reporting module exports."""

from __future__ import annotations

from pathlib import Path

from reporting.batch_plot import (
    DEFAULT_BATCH_PLOT_FILE,
    SUMMARY_FILE_NAME,
    generate_batch_traffic_light_png,
    load_batch_summary,
)
from reporting.context import build_report_context
from schemas.responses import Rob2RunResult


def generate_html_report(result: Rob2RunResult, output_path: Path, pdf_name: str = "Unknown") -> None:
    from reporting.html import generate_html_report as _generate_html_report

    _generate_html_report(result, output_path, pdf_name)


def generate_docx_report(result: Rob2RunResult, output_path: Path, pdf_name: str = "Unknown") -> None:
    from reporting.docx import generate_docx_report as _generate_docx_report

    _generate_docx_report(result, output_path, pdf_name)


def generate_pdf_report(result: Rob2RunResult, output_path: Path, pdf_name: str = "Unknown") -> None:
    from reporting.pdf import generate_pdf_report as _generate_pdf_report

    _generate_pdf_report(result, output_path, pdf_name)


__all__ = [
    "DEFAULT_BATCH_PLOT_FILE",
    "SUMMARY_FILE_NAME",
    "build_report_context",
    "generate_batch_traffic_light_png",
    "generate_docx_report",
    "generate_html_report",
    "generate_pdf_report",
    "load_batch_summary",
]
