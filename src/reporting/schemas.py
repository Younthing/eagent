"""Report generation configuration and output schemas."""

from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ReportOptions(BaseModel):
    """Configuration options for report generation."""

    output_dir: Path | None = None
    output_formats: list[str] = Field(default_factory=lambda: ["html", "docx", "pdf"])
    report_title: str = "ROB2 Risk of Bias Assessment Report"
    include_evidence_text: bool = True
    include_confidence_scores: bool = True
    include_missing_questions: bool = True
    include_validation_reports: bool = False
    include_audit_reports: bool = False
    language: Literal["en", "zh-CN"] = "en"
    template_name: str = "default"
    filename_pattern: str = "rob2_report_{timestamp}"
    pdf_bookmark: bool = True
    pdf_metadata: dict[str, Any] = Field(default_factory=dict)
    docx_page_size: str = "A4"
    html_inline_css: bool = True

    model_config = ConfigDict(extra="forbid")


class ReportMetadata(BaseModel):
    """Metadata about the generated report."""

    generated_at: datetime
    system_version: str
    template_used: str
    formats_requested: list[str]
    file_sizes: dict[str, int] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")


class ReportBundle(BaseModel):
    """Container for generated report outputs."""

    html_path: Path | None = None
    docx_path: Path | None = None
    pdf_path: Path | None = None
    html_content: bytes | None = None
    docx_content: bytes | None = None
    pdf_content: bytes | None = None
    metadata: ReportMetadata
    formats_generated: list[str] = Field(default_factory=list)
    format_errors: dict[str, str] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")


class ReportData(BaseModel):
    """Structured report data optimized for rendering."""

    metadata: "ReportDataMetadata"
    overall: "OverallSection"
    domains: list["DomainSection"]
    citations: "CitationsSection"
    summary_table: str | None = None
    validation_reports: dict[str, Any] | None = None
    audit_reports: list[dict[str, Any]] | None = None

    model_config = ConfigDict(extra="forbid")


class ReportDataMetadata(BaseModel):
    """Report metadata section."""

    title: str
    variant: str
    question_set_version: str
    generated_at: datetime
    system_version: str
    source_pdf_name: str | None = None

    model_config = ConfigDict(extra="forbid")


class OverallSection(BaseModel):
    """Overall risk assessment section."""

    risk: str  # OverallRisk value
    risk_label: str
    rationale: str
    interpretation: str

    model_config = ConfigDict(extra="forbid")


class DomainSection(BaseModel):
    """Domain assessment section."""

    domain_id: str  # DomainId value
    domain_name: str
    effect_type: str | None = None  # EffectType value
    risk: str  # DomainRisk value
    risk_label: str
    risk_rationale: str
    answers: list["QuestionAnswer"]
    missing_questions: list[str]
    total_questions: int
    answered_questions: int

    model_config = ConfigDict(extra="forbid")


class QuestionAnswer(BaseModel):
    """Question answer details."""

    question_id: str
    rob2_id: str
    question_text: str
    answer: str  # AnswerOption value
    answer_label: str
    rationale: str
    evidence_refs: list["EvidenceRef"]
    confidence: float | None = None

    model_config = ConfigDict(extra="forbid")


class EvidenceRef(BaseModel):
    """Evidence reference."""

    paragraph_id: str
    page: int | None = None
    title: str | None = None
    quote: str | None = None

    model_config = ConfigDict(extra="forbid")


class CitationsSection(BaseModel):
    """Citations section with all evidence."""

    citations: list["CitationEntry"]
    total_citations: int
    citations_by_domain: dict[str, int] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")


class CitationEntry(BaseModel):
    """Single citation entry."""

    paragraph_id: str
    page: int | None = None
    title: str | None = None
    text: str
    uses: list["CitationUse"]

    model_config = ConfigDict(extra="forbid")


class CitationUse(BaseModel):
    """Usage information for a citation."""

    domain_id: str
    question_id: str
    rob2_id: str

    model_config = ConfigDict(extra="forbid")
