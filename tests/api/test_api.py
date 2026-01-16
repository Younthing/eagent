from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from api.main import app
from schemas.internal.results import Rob2FinalOutput, Rob2OverallResult
from schemas.responses import Rob2RunResult

client = TestClient(app)


def test_run_endpoint_with_file():
    mock_final_output = Rob2FinalOutput(
        question_set_version="1.0",
        overall=Rob2OverallResult(risk="low", rationale="All good"),
        domains=[],
    )
    mock_result = Rob2RunResult(
        result=mock_final_output,
        table_markdown="| table |",
        runtime_ms=100,
        warnings=[],
    )

    with patch("api.main.run_rob2") as mock_run:
        mock_run.return_value = mock_result

        response = client.post(
            "/run",
            files={"file": ("test.pdf", b"dummy content", "application/pdf")},
            data={"options": '{"debug_level": "min"}'},
        )

        assert response.status_code == 200
        assert response.json()["table_markdown"] == "| table |"
        mock_run.assert_called_once()
        args, _ = mock_run.call_args
        input_data, options_obj = args
        assert input_data.pdf_bytes == b"dummy content"
        assert options_obj.debug_level == "min"


def test_run_endpoint_with_path():
    mock_final_output = Rob2FinalOutput(
        question_set_version="1.0",
        overall=Rob2OverallResult(risk="low", rationale="All good"),
        domains=[],
    )
    mock_result = Rob2RunResult(
        result=mock_final_output,
        table_markdown="| table |",
        runtime_ms=100,
        warnings=[],
    )

    with patch("api.main.run_rob2") as mock_run:
        mock_run.return_value = mock_result

        response = client.post(
            "/run",
            data={"pdf_path": "/tmp/test.pdf"},
        )

        assert response.status_code == 200
        mock_run.assert_called_once()
        args, _ = mock_run.call_args
        input_data, _ = args
        assert input_data.pdf_path == "/tmp/test.pdf"


def test_run_endpoint_validation_error():
    response = client.post("/run")
    assert response.status_code == 400
    assert "Either file or pdf_path must be provided" in response.json()["detail"]

    response = client.post(
        "/run",
        files={"file": ("test.pdf", b"dummy", "application/pdf")},
        data={"pdf_path": "/tmp/test.pdf"},
    )
    assert response.status_code == 400
    assert "Provide only one" in response.json()["detail"]
