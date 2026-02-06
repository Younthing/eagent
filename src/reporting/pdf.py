"""PDF report renderer for ROB2."""

from __future__ import annotations

from pathlib import Path

from reporting.html import render_html
from schemas.responses import Rob2RunResult

try:
    from weasyprint import HTML, CSS

    WEASYPRINT_AVAILABLE = True
except Exception:
    WEASYPRINT_AVAILABLE = False


def generate_pdf_report(result: Rob2RunResult, output_path: Path, pdf_name: str = "Unknown") -> None:
    """Generate PDF report from HTML."""
    if not WEASYPRINT_AVAILABLE:
        print("Warning: WeasyPrint not installed, skipping PDF generation.")
        return

    template_dir = Path(__file__).parent / "templates"
    html_content = render_html(result, pdf_name=pdf_name)

    css = CSS(
        string="""
        .domain-content { display: block !important; }
        .container { box-shadow: none; padding: 0; }
        body { background-color: white; }
    """
    )

    HTML(string=html_content, base_url=str(template_dir)).write_pdf(
        output_path, stylesheets=[css]
    )


__all__ = ["generate_pdf_report", "WEASYPRINT_AVAILABLE"]
