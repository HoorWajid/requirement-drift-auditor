"""
Integration test: exercises the full user journey across multiple endpoints,
unlike unit tests (single function) or security tests (single control).
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


@pytest.mark.integration
def test_full_user_journey():
    r = client.post("/auth/register", json={"email": "journey@test.com", "password": "Passw0rd1"})
    assert r.status_code == 200

    r = client.post("/auth/login", json={"email": "journey@test.com", "password": "Passw0rd1"})
    assert r.status_code == 200
    assert "access_token" in r.cookies

    r = client.post("/analyze", json={
        "req_original": "The system must respond within 2 seconds.",
        "req_updated": "The system must respond within 20 seconds.",
    })
    assert r.status_code == 200
    audit_id = r.json()["audit_id"]
    assert r.json()["severity"] in ("LOW_DRIFT", "MEDIUM_DRIFT", "CONFLICT")

    r = client.get(f"/audits/{audit_id}")
    assert r.status_code == 200

    r = client.post("/chat", json={"audit_id": audit_id, "question": "How many requirements changed?"})
    assert r.status_code == 200
    assert r.json()["answered"] is True

    r = client.post("/auth/logout")
    assert r.status_code == 200
