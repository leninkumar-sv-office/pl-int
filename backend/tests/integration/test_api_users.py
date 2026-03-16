"""Integration tests for user management and version endpoints."""

import pytest


def test_list_users_returns_200(app_client):
    """GET /api/users returns 200."""
    response = app_client.get("/api/users", headers={"X-User-Id": "testuser"})
    assert response.status_code == 200


def test_list_users_returns_list(app_client):
    """GET /api/users returns a list."""
    response = app_client.get("/api/users", headers={"X-User-Id": "testuser"})
    data = response.json()
    assert isinstance(data, list)


def test_list_users_has_test_user(app_client):
    """GET /api/users returns the seeded test user."""
    response = app_client.get("/api/users", headers={"X-User-Id": "testuser"})
    data = response.json()
    ids = [u["id"] for u in data]
    assert "testuser" in ids


def test_list_users_user_shape(app_client):
    """Each user object has required fields."""
    response = app_client.get("/api/users", headers={"X-User-Id": "testuser"})
    users = response.json()
    assert len(users) > 0
    user = users[0]
    assert "id" in user
    assert "name" in user


def test_add_user_returns_200(app_client):
    """POST /api/users adds a new user and returns it."""
    response = app_client.post(
        "/api/users",
        json={"name": "AliceNew", "avatar": "A", "color": "#ff0000"},
        headers={"X-User-Id": "testuser"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "alicenew"
    assert data["name"] == "AliceNew"


def test_add_user_duplicate_returns_400(app_client):
    """POST /api/users with duplicate name returns 400."""
    # First add
    app_client.post(
        "/api/users",
        json={"name": "DupUser"},
        headers={"X-User-Id": "testuser"},
    )
    # Second add — should fail
    response = app_client.post(
        "/api/users",
        json={"name": "DupUser"},
        headers={"X-User-Id": "testuser"},
    )
    assert response.status_code == 400


def test_add_user_missing_name_returns_422(app_client):
    """POST /api/users without 'name' returns 422 validation error."""
    response = app_client.post(
        "/api/users",
        json={"avatar": "X"},
        headers={"X-User-Id": "testuser"},
    )
    assert response.status_code == 422


def test_get_version_returns_200(app_client):
    """GET /api/version returns 200."""
    response = app_client.get("/api/version")
    assert response.status_code == 200


def test_get_version_has_tag(app_client):
    """GET /api/version returns a dict with 'tag' field."""
    response = app_client.get("/api/version")
    data = response.json()
    assert "tag" in data
    assert isinstance(data["tag"], str)


def test_get_version_default_is_dev(app_client):
    """GET /api/version returns 'dev' when no deploy_tag.txt exists."""
    response = app_client.get("/api/version")
    data = response.json()
    # In test environment there is no deploy_tag.txt, so tag should be 'dev'
    assert data["tag"] == "dev"
