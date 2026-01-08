"""HTML formatter with interactive features."""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from reporting.formatters.base import BaseFormatter
from reporting.schemas import ReportData
from reporting.utils import format_timestamp, get_risk_color


class HTMLFormatter(BaseFormatter):
    """Formatter for interactive HTML reports."""

    def __init__(self, template_dir: Path | None = None, inline_assets: bool = True):
        """
        Initialize HTML formatter.

        Args:
            template_dir: Directory containing HTML templates
            inline_assets: Whether to inline CSS and JS (default: True)
        """
        super().__init__(template_dir)
        self.inline_assets = inline_assets
        self._setup_jinja_env()

    def _setup_jinja_env(self) -> None:
        """Setup Jinja2 environment with custom filters."""
        self.jinja_env = Environment(
            loader=FileSystemLoader(str(self.template_dir)),
            autoescape=select_autoescape(["html", "xml"]),
            trim_blocks=True,
            lstrip_blocks=True,
        )

        # Register custom filters
        self.jinja_env.filters["risk_color"] = get_risk_color
        self.jinja_env.filters["format_timestamp"] = lambda dt: format_timestamp(
            dt, "display"
        )

    def format(self, data: ReportData) -> str:
        """Format report data as interactive HTML."""
        template = self.jinja_env.get_template("report.html.j2")

        # Load CSS and JS if inline mode
        css_content = ""
        js_content = ""

        if self.inline_assets:
            css_path = self.template_dir / "styles.css"
            if css_path.exists():
                css_content = css_path.read_text(encoding="utf-8")

            js_path = self.template_dir / "interactive.js"
            if js_path.exists():
                js_content = js_path.read_text(encoding="utf-8")

        return template.render(
            data=data,
            inline_css=css_content if self.inline_assets else None,
            inline_js=js_content if self.inline_assets else None,
        )
