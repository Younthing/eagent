"""Markdown formatter for PDF and DOCX generation."""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from reporting.formatters.base import BaseFormatter
from reporting.schemas import ReportData
from reporting.utils import format_timestamp


class MarkdownFormatter(BaseFormatter):
    """Formatter for Markdown documents (source for PDF/DOCX)."""

    def __init__(self, template_dir: Path | None = None):
        """
        Initialize Markdown formatter.

        Args:
            template_dir: Directory containing Markdown templates
        """
        super().__init__(template_dir)
        self._setup_jinja_env()

    def _setup_jinja_env(self) -> None:
        """Setup Jinja2 environment for Markdown."""
        self.jinja_env = Environment(
            loader=FileSystemLoader(str(self.template_dir)),
            trim_blocks=True,
            lstrip_blocks=True,
        )

        # Register custom filters
        self.jinja_env.filters["format_timestamp"] = lambda dt: format_timestamp(
            dt, "display"
        )
        self.jinja_env.filters["escape_md"] = self._escape_markdown

    def format(self, data: ReportData) -> str:
        """Format report data as Markdown."""
        template = self.jinja_env.get_template("report.md.j2")
        return template.render(data=data)

    def _escape_markdown(self, text: str) -> str:
        """Escape special Markdown characters."""
        if not text:
            return ""

        # Escape common Markdown special characters
        replacements = {
            "\\": "\\\\",
            "`": "\\`",
            "*": "\\*",
            "_": "\\_",
            "[": "\\[",
            "]": "\\]",
            "<": "\\<",
            ">": "\\>",
            "#": "\\#",
            "|": "\\|",
        }

        for char, escaped in replacements.items():
            text = text.replace(char, escaped)

        return text
