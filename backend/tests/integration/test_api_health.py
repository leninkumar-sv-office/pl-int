"""Integration tests for GET /health endpoint."""

import pytest


def test_health_returns_200_or_503(app_client):
    """Health check always responds (200 healthy or 503 unhealthy)."""
    response = app_client.get("/health")
    assert response.status_code in (200, 503)


def test_health_response_shape(app_client):
    """Health response contains required top-level fields."""
    response = app_client.get("/health")
    data = response.json()
    assert "status" in data
    assert "tag" in data
    assert "checks" in data


def test_health_status_value(app_client):
    """Health status is either 'healthy' or 'unhealthy'."""
    response = app_client.get("/health")
    data = response.json()
    assert data["status"] in ("healthy", "unhealthy")


def test_health_tag_is_string(app_client):
    """Health tag is a string (e.g. 'dev')."""
    response = app_client.get("/health")
    data = response.json()
    assert isinstance(data["tag"], str)
    assert len(data["tag"]) > 0


def test_health_checks_contains_subsystems(app_client):
    """Health checks dict contains subsystem keys."""
    response = app_client.get("/health")
    data = response.json()
    checks = data["checks"]
    # At minimum stocks and auth should be present
    assert "stocks" in checks
    assert "auth" in checks


def test_health_checks_stocks_shape(app_client):
    """Stocks check has a status field."""
    response = app_client.get("/health")
    checks = response.json()["checks"]
    assert "status" in checks["stocks"]


def test_health_checks_auth_mode(app_client):
    """Auth check reports 'local' mode in test environment."""
    response = app_client.get("/health")
    checks = response.json()["checks"]
    auth_check = checks.get("auth", {})
    if "mode" in auth_check:
        assert auth_check["mode"] == "local"


def test_health_no_auth_required(app_client):
    """Health endpoint must not require authentication."""
    # No Authorization header sent — should still respond
    response = app_client.get("/health")
    assert response.status_code != 401
    assert response.status_code != 403
