"""Utility functions for report generation."""

import shutil
import subprocess
from typing import Literal

from schemas.internal.decisions import AnswerOption, DomainRisk
from schemas.internal.results import OverallRisk


def get_risk_label(risk: DomainRisk | OverallRisk) -> str:
    """Get human-readable label for risk level."""
    mapping = {
        "high": "High",
        "some_concerns": "Some concerns",
        "low": "Low",
    }
    return mapping.get(risk, str(risk))


def get_risk_color(risk: DomainRisk | OverallRisk) -> str:
    """Get color code for risk level (for HTML/CSS)."""
    mapping = {
        "high": "#dc3545",  # Red
        "some_concerns": "#ffc107",  # Yellow
        "low": "#28a745",  # Green
    }
    return mapping.get(risk, "#6c757d")  # Gray for unknown


def get_answer_label(answer: AnswerOption) -> str:
    """Get human-readable label for answer option."""
    mapping = {
        "Y": "Yes",
        "PY": "Probably Yes",
        "PN": "Probably No",
        "N": "No",
        "NI": "No Information",
        "NA": "Not Applicable",
    }
    return mapping.get(answer, str(answer))


def get_domain_name(domain_id: str) -> str:
    """Get full domain name from domain ID."""
    domain_names = {
        "D1": "Randomization Process",
        "D2": "Deviations from Intended Interventions",
        "D3": "Missing Outcome Data",
        "D4": "Measurement of the Outcome",
        "D5": "Selection of the Reported Result",
    }
    return domain_names.get(domain_id, domain_id)


def get_overall_interpretation(risk: OverallRisk) -> str:
    """Get interpretation text for overall risk level."""
    interpretations = {
        "low": (
            "The study is judged to be at low risk of bias for all domains "
            "for this result."
        ),
        "some_concerns": (
            "The study is judged to raise some concerns in at least one domain "
            "for this result, but not to be at high risk of bias for any domain."
        ),
        "high": (
            "The study is judged to be at high risk of bias in at least one domain "
            "for this result, or the study is judged to have some concerns for "
            "multiple domains in a way that substantially lowers confidence in the result."
        ),
    }
    return interpretations.get(risk, "")


def check_pandoc_available() -> tuple[bool, str | None]:
    """
    Check if Pandoc is available on the system.

    Returns:
        Tuple of (is_available, version)
    """
    if not shutil.which("pandoc"):
        return False, None

    try:
        result = subprocess.run(
            ["pandoc", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if result.returncode == 0:
            version_line = result.stdout.split("\n")[0]
            version = version_line.split()[1] if len(version_line.split()) > 1 else None
            return True, version
        return False, None
    except Exception:
        return False, None


def check_latex_engine(engine: str = "xelatex") -> bool:
    """Check if a LaTeX engine is available."""
    return shutil.which(engine) is not None


def get_available_pdf_engine() -> str | None:
    """
    Get the first available PDF engine.

    Priority: xelatex > lualatex > pdflatex
    """
    for engine in ["xelatex", "lualatex", "pdflatex"]:
        if check_latex_engine(engine):
            return engine
    return None


def check_font_available(font_name: str) -> bool:
    """
    Check if a font is available on the system.

    This is a basic check using fc-list on Unix-like systems.
    """
    if not shutil.which("fc-list"):
        # Cannot check fonts without fc-list
        return False

    try:
        result = subprocess.run(
            ["fc-list", ":", "family"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if result.returncode == 0:
            fonts = result.stdout.lower()
            return font_name.lower() in fonts
        return False
    except Exception:
        return False


def get_recommended_cjk_font() -> str:
    """
    Get a recommended CJK font that is likely available.

    Checks in order: Noto Sans CJK SC, Source Han Sans, system defaults.
    """
    candidates = [
        "Noto Sans CJK SC",
        "Source Han Sans SC",
        "SimSun",
        "SimHei",
    ]

    for font in candidates:
        if check_font_available(font):
            return font

    # Fallback
    return "Noto Sans CJK SC"


def sanitize_filename(name: str) -> str:
    """Sanitize a string for use in filenames."""
    # Remove or replace invalid filename characters
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        name = name.replace(char, "_")
    return name.strip()


def format_timestamp(dt: object, fmt: Literal["file", "display"] = "file") -> str:
    """Format a datetime for use in filenames or display."""
    from datetime import datetime

    if not isinstance(dt, datetime):
        dt = datetime.now()

    if fmt == "file":
        return dt.strftime("%Y%m%d_%H%M%S")
    else:
        return dt.strftime("%Y-%m-%d %H:%M:%S")
