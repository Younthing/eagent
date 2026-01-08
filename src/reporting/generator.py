"""Report generator coordinating formatters and output."""

from datetime import datetime
from typing import Any

from reporting.builder import ReportDataBuilder
from reporting.formatters import HTMLFormatter, MarkdownFormatter
from reporting.pandoc_runner import PandocRunner
from reporting.schemas import ReportBundle, ReportMetadata, ReportOptions
from reporting.utils import format_timestamp, sanitize_filename
from schemas.internal.results import Rob2FinalOutput


class ReportGenerator:
    """Main report generator coordinating format conversion."""

    def __init__(self, options: ReportOptions):
        """
        Initialize report generator.

        Args:
            options: Report generation configuration
        """
        self.options = options
        self.pandoc_runner = PandocRunner()

    def generate(
        self,
        result: Rob2FinalOutput,
        *,
        table_markdown: str | None = None,
        validation_reports: dict[str, Any] | None = None,
        audit_reports: list[dict[str, Any]] | None = None,
    ) -> ReportBundle:
        """
        Generate reports in configured formats.

        Args:
            result: ROB2 assessment result
            table_markdown: Optional markdown table
            validation_reports: Optional validation reports
            audit_reports: Optional audit reports

        Returns:
            ReportBundle with generated report paths/content
        """
        # Build structured report data
        builder = ReportDataBuilder(
            result,
            report_title=self.options.report_title,
            table_markdown=table_markdown,
            validation_reports=validation_reports
            if self.options.include_validation_reports
            else None,
            audit_reports=audit_reports
            if self.options.include_audit_reports
            else None,
            include_confidence=self.options.include_confidence_scores,
        )
        report_data = builder.build()

        # Prepare bundle metadata
        bundle_metadata = ReportMetadata(
            generated_at=datetime.now(),
            system_version=report_data.metadata.system_version,
            template_used=self.options.template_name,
            formats_requested=self.options.output_formats,
        )

        bundle = ReportBundle(metadata=bundle_metadata)

        # Generate base filename
        timestamp = format_timestamp(bundle_metadata.generated_at, "file")
        base_filename = self.options.filename_pattern.format(timestamp=timestamp)
        base_filename = sanitize_filename(base_filename)

        # Track errors
        format_errors: dict[str, str] = {}

        # Generate HTML if requested
        if "html" in self.options.output_formats:
            try:
                html_content = self._generate_html(report_data)
                if self.options.output_dir:
                    html_path = self.options.output_dir / f"{base_filename}.html"
                    html_path.parent.mkdir(parents=True, exist_ok=True)
                    html_path.write_text(html_content, encoding="utf-8")
                    bundle.html_path = html_path
                    bundle.metadata.file_sizes["html"] = len(html_content)
                else:
                    bundle.html_content = html_content.encode("utf-8")
                bundle.formats_generated.append("html")
            except Exception as e:
                format_errors["html"] = str(e)

        # Generate Markdown-based formats (PDF, DOCX)
        markdown_formats = [
            fmt for fmt in self.options.output_formats if fmt in ["pdf", "docx"]
        ]

        if markdown_formats:
            try:
                markdown_content = self._generate_markdown(report_data)

                # Save markdown to temp location if needed for conversion
                if self.options.output_dir:
                    md_path = self.options.output_dir / f"{base_filename}.md"
                    md_path.parent.mkdir(parents=True, exist_ok=True)
                    md_path.write_text(markdown_content, encoding="utf-8")

                    # Generate metadata.yaml
                    metadata_path = self.options.output_dir / "metadata.yaml"
                    self.pandoc_runner.generate_metadata_yaml(
                        metadata_path,
                        title=self.options.report_title,
                        lang=self.options.language,
                        **self.options.pdf_metadata,
                    )

                    # Convert to PDF
                    if "pdf" in markdown_formats:
                        pdf_path = self.options.output_dir / f"{base_filename}.pdf"
                        if self.pandoc_runner.convert_to_pdf(
                            md_path, pdf_path, metadata_path=metadata_path
                        ):
                            bundle.pdf_path = pdf_path
                            bundle.formats_generated.append("pdf")
                            bundle.metadata.file_sizes["pdf"] = pdf_path.stat().st_size
                        else:
                            format_errors["pdf"] = "Pandoc conversion failed"

                    # Convert to DOCX
                    if "docx" in markdown_formats:
                        docx_path = self.options.output_dir / f"{base_filename}.docx"
                        if self.pandoc_runner.convert_to_docx(
                            md_path, docx_path, metadata_path=metadata_path
                        ):
                            bundle.docx_path = docx_path
                            bundle.formats_generated.append("docx")
                            bundle.metadata.file_sizes["docx"] = (
                                docx_path.stat().st_size
                            )
                        else:
                            format_errors["docx"] = "Pandoc conversion failed"

                    # Clean up temporary markdown and metadata files
                    md_path.unlink(missing_ok=True)
                    metadata_path.unlink(missing_ok=True)
                else:
                    # In-memory mode not fully supported for PDF/DOCX
                    # Would need temp files
                    for fmt in markdown_formats:
                        format_errors[fmt] = "In-memory mode not supported for " + fmt

            except Exception as e:
                for fmt in markdown_formats:
                    format_errors[fmt] = str(e)

        bundle.format_errors = format_errors
        return bundle

    def _generate_html(self, data: Any) -> str:
        """Generate HTML report."""
        formatter = HTMLFormatter(inline_assets=self.options.html_inline_css)
        return formatter.format(data)

    def _generate_markdown(self, data: Any) -> str:
        """Generate Markdown report."""
        formatter = MarkdownFormatter()
        return formatter.format(data)
