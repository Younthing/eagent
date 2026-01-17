from unittest.mock import patch
from fastapi.testclient import TestClient
from api.main import app
from schemas.responses import Rob2RunResult
from schemas.internal.results import Rob2FinalOutput, Rob2OverallResult

client = TestClient(app)

@patch("api.actions.graph.run_rob2")
def test_run_pipeline(mock_run):
    # Mock return value
    mock_result = Rob2RunResult(
        result=Rob2FinalOutput(
            question_set_version="1.0",
            overall=Rob2OverallResult(risk="low", rationale="test"),
            domains=[],
            citations=[]
        ),
        table_markdown="| test |",
        runtime_ms=100
    )
    mock_run.return_value = mock_result
    
    files = {'file': ('test.pdf', b'%PDF-1.4 dummy content', 'application/pdf')}
    
    response = client.post("/graph/run", files=files)
    
    assert response.status_code == 200
    assert response.json()["result"]["overall"]["risk"] == "low"
    mock_run.assert_called_once()
