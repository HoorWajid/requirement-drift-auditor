"""
Security-focused tests — run these FIRST, before functional tests, since a
security failure here invalidates trust in everything downstream.
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def _register_and_login(email="user1@test.com", password="Passw0rd1"):
    client.post("/auth/register", json={"email": email, "password": password})
    r = client.post("/auth/login", json={"email": email, "password": password})
    return r


@pytest.mark.security
def test_weak_password_rejected():
    r = client.post("/auth/register", json={"email": "a@test.com", "password": "weak"})
    assert r.status_code == 422  # Pydantic validation failure, not 500


@pytest.mark.security
def test_unauthenticated_analyze_blocked():
    r = client.post("/analyze", json={"req_original": "a", "req_updated": "b"})
    assert r.status_code == 401


@pytest.mark.security
def test_idor_protection():
    r1 = _register_and_login("victim@test.com", "Passw0rd1")
    assert r1.status_code == 200
    r_analyze = client.post(
        "/analyze",
        json={"req_original": "respond within 2 seconds", "req_updated": "respond within 200 seconds"},
    )
    audit_id = r_analyze.json()["audit_id"]
    client.post("/auth/logout")

    _register_and_login("attacker@test.com", "Passw0rd1")
    r_steal = client.get(f"/audits/{audit_id}")
    assert r_steal.status_code == 404  # must NOT be able to read victim's audit


@pytest.mark.security
def test_oversized_input_rejected():
    _register_and_login("user3@test.com", "Passw0rd1")
    huge_text = "a" * 6000
    r = client.post("/analyze", json={"req_original": huge_text, "req_updated": "short"})
    assert r.status_code == 422


@pytest.mark.security
def test_login_rate_limit():
    for _ in range(11):
        r = client.post("/auth/login", json={"email": "nouser@test.com", "password": "wrong"})
    assert r.status_code == 429  # eventually throttled
