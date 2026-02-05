import importlib
import sys
from unittest.mock import MagicMock

import pytest

from schemas.responses import Rob2RunResult
from schemas.internal.results import (
    Rob2FinalOutput,
    Rob2OverallResult,
    Rob2DomainResult,
    Rob2AnswerResult,
)


@pytest.fixture
def reports_module(monkeypatch):
    # Mock heavy dependencies before importing services.reports
    monkeypatch.setitem(sys.modules, "torch", MagicMock())
    monkeypatch.setitem(sys.modules, "langgraph", MagicMock())
    monkeypatch.setitem(sys.modules, "langgraph.graph", MagicMock())

    # Mock internal modules that cause import chains
    mock_runner = MagicMock()
    mock_runner.run_rob2 = MagicMock()
    monkeypatch.setitem(sys.modules, "services.rob2_runner", mock_runner)

    import services.reports as reports

    importlib.reload(reports)
    return reports

@pytest.fixture
def mock_result():
    return Rob2RunResult(
        result=Rob2FinalOutput(
            question_set_version="1.0",
            overall=Rob2OverallResult(risk="low", rationale="Overall rationale"),
            domains=[
                Rob2DomainResult(
                    domain="D1",
                    risk="low",
                    risk_rationale="Domain 1 rationale",
                    rule_trace=["D1:R1 q1_2 in NO -> high"],
                    answers=[
                        Rob2AnswerResult(
                            question_id="1.1",
                            answer="Y",
                            rationale="Answer rationale",
                            evidence_refs=[]
                        )
                    ]
                )
            ]
        ),
        table_markdown="| Table |",
        reports={},
        audit_reports=[],
        debug={},
        runtime_ms=100
    )

def test_generate_html_report(mock_result, tmp_path, reports_module):
    output_path = tmp_path / "report.html"
    reports_module.generate_html_report(mock_result, output_path, "test.pdf")
    assert output_path.exists()
    content = output_path.read_text(encoding="utf-8")
    assert "ROB2 风险偏倚评估报告" in content
    assert "Domain 1 rationale" in content
    assert "规则路径" in content

def test_generate_docx_report(mock_result, tmp_path, reports_module):
    output_path = tmp_path / "report.docx"
    reports_module.generate_docx_report(mock_result, output_path, "test.pdf")
    assert output_path.exists()

def test_generate_pdf_report(mock_result, tmp_path, reports_module):
    output_path = tmp_path / "report.pdf"
    reports_module.generate_pdf_report(mock_result, output_path, "test.pdf")
    if output_path.exists():
        assert output_path.stat().st_size > 0


def test_render_html_includes_rule_trace(mock_result):
    from reporting.html import render_html

    content = render_html(mock_result, pdf_name="test.pdf")
    assert "规则路径" in content
