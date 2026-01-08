"""Pandoc wrapper for document conversion."""

import subprocess
from pathlib import Path
from typing import Any

from reporting.utils import (
    check_pandoc_available,
    get_available_pdf_engine,
    get_recommended_cjk_font,
)


class PandocRunner:
    """Wrapper for Pandoc document conversion."""

    def __init__(self):
        self.pandoc_available, self.pandoc_version = check_pandoc_available()
        self.pdf_engine = get_available_pdf_engine()

    def is_available(self) -> bool:
        """Check if Pandoc is available."""
        return self.pandoc_available

    def can_generate_pdf(self) -> bool:
        """Check if PDF generation is supported."""
        return self.pandoc_available and self.pdf_engine is not None

    def convert_to_pdf(
        self,
        markdown_path: Path,
        output_path: Path,
        *,
        metadata_path: Path | None = None,
        template_path: Path | None = None,
        toc: bool = True,
        toc_depth: int = 3,
        number_sections: bool = True,
        extra_args: list[str] | None = None,
    ) -> bool:
        """
        Convert Markdown to PDF using Pandoc.

        Returns True if successful, False otherwise.
        """
        if not self.can_generate_pdf():
            return False

        cmd = [
            "pandoc",
            str(markdown_path),
            "--pdf-engine",
            self.pdf_engine or "xelatex",
            "-o",
            str(output_path),
        ]

        if metadata_path:
            cmd.extend(["--metadata-file", str(metadata_path)])

        if template_path:
            cmd.extend(["--template", str(template_path)])

        if toc:
            cmd.append("--toc")
            cmd.extend(["--toc-depth", str(toc_depth)])

        if number_sections:
            cmd.append("--number-sections")

        # Add geometry and font settings
        cmd.extend(["-V", "geometry:margin=2.5cm", "-V", "fontsize=11pt"])

        if extra_args:
            cmd.extend(extra_args)

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )
            return result.returncode == 0
        except Exception:
            return False

    def convert_to_docx(
        self,
        markdown_path: Path,
        output_path: Path,
        *,
        metadata_path: Path | None = None,
        reference_doc: Path | None = None,
        toc: bool = True,
        number_sections: bool = True,
        extra_args: list[str] | None = None,
    ) -> bool:
        """
        Convert Markdown to DOCX using Pandoc.

        Returns True if successful, False otherwise.
        """
        if not self.is_available():
            return False

        cmd = [
            "pandoc",
            str(markdown_path),
            "--to",
            "docx",
            "-o",
            str(output_path),
        ]

        if metadata_path:
            cmd.extend(["--metadata-file", str(metadata_path)])

        if reference_doc:
            cmd.extend(["--reference-doc", str(reference_doc)])

        if toc:
            cmd.append("--toc")

        if number_sections:
            cmd.append("--number-sections")

        if extra_args:
            cmd.extend(extra_args)

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            return result.returncode == 0
        except Exception:
            return False

    def generate_metadata_yaml(
        self,
        output_path: Path,
        *,
        title: str = "ROB2 Risk of Bias Assessment Report",
        author: str = "ROB2 Automated Assessment System",
        date: str | None = None,
        lang: str = "en-US",
        mainfont: str | None = None,
        **extra_metadata: Any,
    ) -> None:
        """Generate metadata.yaml file for Pandoc."""
        import yaml
        from datetime import datetime

        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        if mainfont is None:
            mainfont = get_recommended_cjk_font()

        metadata = {
            "title": title,
            "author": author,
            "date": date,
            "lang": lang,
            "mainfont": mainfont,
            "sansfont": mainfont,
            "monofont": "Courier New",
            "CJKmainfont": mainfont,
            "CJKsansfont": mainfont,
            "CJKmonofont": "Noto Sans Mono CJK SC",
            "geometry": ["margin=2.5cm", "a4paper"],
            "fontsize": "11pt",
            "documentclass": "article",
            "papersize": "a4",
            "toc": True,
            "toc-depth": 3,
            "number-sections": True,
            "colorlinks": True,
            "linkcolor": "blue",
            "urlcolor": "blue",
            "citecolor": "blue",
            "html-math-method": "mathjax",
            "pdf-bookmarks": True,
            "pdf-bookmarks-open-level": 2,
        }

        # Merge extra metadata
        metadata.update(extra_metadata)

        with open(output_path, "w", encoding="utf-8") as f:
            yaml.dump(metadata, f, allow_unicode=True, sort_keys=False)
