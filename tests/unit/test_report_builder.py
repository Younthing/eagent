"""Unit tests for ReportDataBuilder."""

from datetime import datetime

import pytest

from reporting.builder import ReportDataBuilder
from schemas.internal.decisions import AnswerOption, DomainRisk  # noqa: F401 - type aliases
from schemas.internal.locator import DomainId
from schemas.internal.results import (
    Citation,
    CitationUse,
    Rob2AnswerResult,
    Rob2DomainResult,
    Rob2FinalOutput,
    Rob2OverallResult,
)


@pytest.fixture
def sample_rob2_output() -> Rob2FinalOutput:
    """Create a sample Rob2FinalOutput for testing."""
    return Rob2FinalOutput(
        variant="standard",
        question_set_version="2.0",
        overall=Rob2OverallResult(
            risk="low",
            rationale="All domains are at low risk",
        ),
        domains=[
            Rob2DomainResult(
                domain="D1",
                risk="low",
                risk_rationale="Randomization was properly conducted",
                answers=[
                    Rob2AnswerResult(
                        question_id="1.1",
                        rob2_id="1.1",
                        text="Was the allocation sequence random?",
                        answer="Y",
                        rationale="Computer-generated randomization was used",
                        evidence_refs=[],
                        confidence=0.95,
                    )
                ],
                missing_questions=["1.3"],
            ),
            Rob2DomainResult(
                domain="D2",
                effect_type="assignment",
                risk="low",
                risk_rationale="No deviations detected",
                answers=[],
                missing_questions=[],
            ),
        ],
        citations=[
            Citation(
                paragraph_id="p123",
                page=5,
                title="Methods",
                text="Randomization was computer-generated",
                uses=[
                    CitationUse(
                        domain="D1",
                        question_id="1.1",
                        quote="computer-generated",
                    )
                ],
            )
        ],
    )


def test_builder_metadata(sample_rob2_output: Rob2FinalOutput) -> None:
    """Test metadata generation."""
    builder = ReportDataBuilder(
        sample_rob2_output,
        report_title="Test Report",
        source_pdf_name="test.pdf",
    )
    report_data = builder.build()

    assert report_data.metadata.title == "Test Report"
    assert report_data.metadata.variant == "standard"
    assert report_data.metadata.question_set_version == "2.0"
    assert report_data.metadata.source_pdf_name == "test.pdf"
    assert isinstance(report_data.metadata.generated_at, datetime)


def test_builder_overall_section(sample_rob2_output: Rob2FinalOutput) -> None:
    """Test overall risk section."""
    builder = ReportDataBuilder(sample_rob2_output)
    report_data = builder.build()

    assert report_data.overall.risk == "low"
    assert report_data.overall.risk_label == "Low"
    assert report_data.overall.rationale == "All domains are at low risk"
    assert "low risk of bias for all domains" in report_data.overall.interpretation


def test_builder_domains(sample_rob2_output: Rob2FinalOutput) -> None:
    """Test domain sections."""
    builder = ReportDataBuilder(sample_rob2_output)
    report_data = builder.build()

    assert len(report_data.domains) == 2

    # Check D1
    d1 = report_data.domains[0]
    assert d1.domain_id == "D1"
    assert d1.domain_name == "Randomization Process"
    assert d1.risk == "low"
    assert d1.risk_label == "Low"
    assert len(d1.answers) == 1
    assert len(d1.missing_questions) == 1
    assert d1.total_questions == 2
    assert d1.answered_questions == 1

    # Check D2
    d2 = report_data.domains[1]
    assert d2.domain_id == "D2"
    assert d2.effect_type == "assignment"


def test_builder_question_answers(sample_rob2_output: Rob2FinalOutput) -> None:
    """Test question answer conversion."""
    builder = ReportDataBuilder(sample_rob2_output)
    report_data = builder.build()

    answer = report_data.domains[0].answers[0]
    assert answer.question_id == "1.1"
    assert answer.rob2_id == "1.1"
    assert answer.question_text == "Was the allocation sequence random?"
    assert answer.answer == "Y"
    assert answer.answer_label == "Yes"
    assert answer.confidence == 0.95


def test_builder_citations(sample_rob2_output: Rob2FinalOutput) -> None:
    """Test citations section."""
    builder = ReportDataBuilder(sample_rob2_output)
    report_data = builder.build()

    assert report_data.citations.total_citations == 1
    assert "D1" in report_data.citations.citations_by_domain

    citation = report_data.citations.citations[0]
    assert citation.paragraph_id == "p123"
    assert citation.page == 5
    assert citation.title == "Methods"
    assert citation.text == "Randomization was computer-generated"
    assert len(citation.uses) == 1
    assert citation.uses[0].domain_id == "D1"


def test_builder_confidence_disabled(sample_rob2_output: Rob2FinalOutput) -> None:
    """Test confidence scores can be disabled."""
    builder = ReportDataBuilder(sample_rob2_output, include_confidence=False)
    report_data = builder.build()

    answer = report_data.domains[0].answers[0]
    assert answer.confidence is None


def test_builder_with_table_markdown(sample_rob2_output: Rob2FinalOutput) -> None:
    """Test including table markdown."""
    builder = ReportDataBuilder(
        sample_rob2_output,
        table_markdown="| Domain | Risk |\n|--------|------|",
    )
    report_data = builder.build()

    assert report_data.summary_table == "| Domain | Risk |\n|--------|------|"
