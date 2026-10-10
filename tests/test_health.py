"""Health endpoint tests for B01.

Verifies the exact contract from CONTRACT.md:
    GET /api/health -> {"status": "ok", "schema_version": "0.1"}
"""

from fastapi.testclient import TestClient

from backend.app import app

client = TestClient(app)


def test_health_returns_ok_and_schema_version():
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body == {"status": "ok", "schema_version": "0.1"}
