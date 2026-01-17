from unittest.mock import patch
from fastapi.testclient import TestClient
from api.main import app
from schemas.internal.documents import DocStructure

client = TestClient(app)

@patch("api.actions.preprocess.load_doc_structure")
def test_preprocess(mock_load):
    # Mock return value
    mock_doc = DocStructure(body="test content", sections=[])
    mock_load.return_value = mock_doc
    
    # Create a dummy file
    # PDF signature usually required but for mock it doesn't matter what the content is, 
    # unless we validate content before calling load_doc_structure (we only check extension).
    files = {'file': ('test.pdf', b'%PDF-1.4 dummy content', 'application/pdf')}
    
    response = client.post("/preprocess", files=files)
    
    assert response.status_code == 200
    assert response.json()["body"] == "test content"
    mock_load.assert_called_once()
