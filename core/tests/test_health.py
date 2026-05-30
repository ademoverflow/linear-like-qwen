from core.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_health() -> None:
    """Test health endpoint."""
    response = client.get("/health")
    status_code = 200
    assert response.status_code == status_code
    data = response.json()
    assert data["status"] == "ok"
    assert "uptime" in data
    assert data["uptime"] > 0
