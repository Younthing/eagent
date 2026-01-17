from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)

def test_config():
    response = client.get("/config")
    assert response.status_code == 200
    data = response.json()
    assert "docling_layout_model" in data
