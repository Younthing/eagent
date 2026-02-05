"""Report generation services for ROB2 (compat wrappers)."""

from __future__ import annotations

from pathlib import Path

from schemas.responses import Rob2RunResult


def generate_html_report(result: Rob2RunResult, output_path: Path, pdf_name: str = "Unknown") -> None:
    """Generate interactive HTML report."""
    from reporting.html import generate_html_report as _generate_html_report

    _generate_html_report(result, output_path, pdf_name)


def generate_pdf_report(result: Rob2RunResult, output_path: Path, pdf_name: str = "Unknown") -> None:
    """Generate PDF report from HTML."""
    from reporting.pdf import generate_pdf_report as _generate_pdf_report

    _generate_pdf_report(result, output_path, pdf_name)


def generate_docx_report(result: Rob2RunResult, output_path: Path, pdf_name: str = "Unknown") -> None:
    """Generate Word (docx) report."""
    from reporting.docx import generate_docx_report as _generate_docx_report

    _generate_docx_report(result, output_path, pdf_name)


__all__ = ["generate_html_report", "generate_pdf_report", "generate_docx_report"]
