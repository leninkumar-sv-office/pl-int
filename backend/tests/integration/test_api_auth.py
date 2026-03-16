"""Integration tests for authentication endpoints."""

import pytest


def test_auth_status_returns_200(app_client):
    """GET /api/auth/status returns 200."""
    response = app_client.get("/api/auth/status")
    assert response.status_code == 200


def test_auth_status_shape(app_client):
    """Auth status response has required fields."""
    response = app_client.get("/api/auth/status")
    data = response.json()
    assert "auth_enabled" in data
    assert "auth_mode" in data
    assert "google_client_id" in data


def test_auth_status_local_mode(app_client):
    """Auth mode is 'local' in test environment."""
    response = app_client.get("/api/auth/status")
    data = response.json()
    assert data["auth_mode"] == "local"
    assert data["auth_enabled"] is False


def test_auth_verify_no_token_returns_401(app_client):
    """GET /api/auth/verify with no token returns 401."""
    response = app_client.get("/api/auth/verify")
    assert response.status_code == 401


def test_auth_verify_invalid_token_returns_401(app_client):
    """GET /api/auth/verify with garbage token returns 401."""
    response = app_client.get(
        "/api/auth/verify",
        headers={"Authorization": "Bearer totally-invalid-token"},
    )
    assert response.status_code == 401


def test_auth_verify_valid_token(app_client, auth_token):
    """GET /api/auth/verify with a valid JWT returns 200 and payload."""
    response = app_client.get(
        "/api/auth/verify",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "email" in data
    assert data["email"] == "test@example.com"


def test_auth_verify_response_has_name(app_client, auth_token):
    """Verify response includes the user's name."""
    response = app_client.get(
        "/api/auth/verify",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "name" in data


def test_google_login_disabled_in_local_mode(app_client):
    """POST /api/auth/google returns 400 when AUTH_MODE=local."""
    response = app_client.post(
        "/api/auth/google",
        json={"token": "some-google-id-token"},
    )
    assert response.status_code == 400


def test_google_login_missing_token(app_client):
    """POST /api/auth/google with empty token returns 400."""
    response = app_client.post(
        "/api/auth/google",
        json={"token": ""},
    )
    assert response.status_code == 400
