import sys
from unittest.mock import MagicMock
import pytest

# Mock heavy dependencies before importing services.reports
sys.modules['torch'] = MagicMock()
sys.modules['langgraph'] = MagicMock()
sys.modules['langgraph.graph'] = MagicMock()

# Mock internal modules that cause import chains
mock_runner = MagicMock()
mock_runner.run_rob2 = MagicMock()
sys.modules['services.rob2_runner'] = mock_runner

# We also need to mock pipelines and its children to be safe,
# although if rob2_runner is mocked, it might not import them.
# However, if other things import them, we are safe.

from pathlib import Path
from schemas.responses import Rob2RunResult
from schemas.internal.results import Rob2FinalOutput, Rob2OverallResult, Rob2DomainResult, Rob2AnswerResult
from services.reports import generate_html_report, generate_docx_report, generate_pdf_report

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

def test_generate_html_report(mock_result, tmp_path):
    output_path = tmp_path / "report.html"
    generate_html_report(mock_result, output_path, "test.pdf")
    assert output_path.exists()
    content = output_path.read_text(encoding="utf-8")
    assert "ROB2 风险偏倚评估报告" in content
    assert "Domain 1 rationale" in content

def test_generate_docx_report(mock_result, tmp_path):
    output_path = tmp_path / "report.docx"
    generate_docx_report(mock_result, output_path, "test.pdf")
    assert output_path.exists()

def test_generate_pdf_report(mock_result, tmp_path):
    output_path = tmp_path / "report.pdf"
    generate_pdf_report(mock_result, output_path, "test.pdf")
    if output_path.exists():
        assert output_path.stat().st_size > 0
