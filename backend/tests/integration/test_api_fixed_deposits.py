"""Integration tests for Fixed Deposit CRUD endpoints."""

import pytest
import json
import hashlib

HEADERS = {"X-User-Id": "testuser"}

FD_PAYLOAD = {
    "bank": "SBI",
    "principal": 100000.0,
    "interest_rate": 7.5,
    "tenure_months": 12,
    "start_date": "2024-01-01",
    "maturity_date": "2025-01-01",
    "status": "Active",
}


# ── GET /api/fixed-deposits/summary ─────────────────────────────────────────

def test_fd_summary_returns_200(app_client):
    """GET /api/fixed-deposits/summary returns 200."""
    response = app_client.get("/api/fixed-deposits/summary", headers=HEADERS)
    assert response.status_code == 200


def test_fd_summary_empty(app_client):
    """GET /api/fixed-deposits/summary returns empty list initially."""
    response = app_client.get("/api/fixed-deposits/summary", headers=HEADERS)
    data = response.json()
    assert isinstance(data, list)
    assert data == []


# ── GET /api/fixed-deposits/dashboard ───────────────────────────────────────

def test_fd_dashboard_returns_200(app_client):
    """GET /api/fixed-deposits/dashboard returns 200."""
    response = app_client.get("/api/fixed-deposits/dashboard", headers=HEADERS)
    assert response.status_code == 200


def test_fd_dashboard_shape(app_client):
    """Dashboard response is a dict."""
    response = app_client.get("/api/fixed-deposits/dashboard", headers=HEADERS)
    data = response.json()
    assert isinstance(data, dict)


# ── POST /api/fixed-deposits/add ────────────────────────────────────────────

def test_add_fd_returns_200(app_client):
    """POST /api/fixed-deposits/add returns 200."""
    response = app_client.post(
        "/api/fixed-deposits/add",
        json=FD_PAYLOAD,
        headers=HEADERS,
    )
    assert response.status_code == 200


def test_add_fd_response_has_id(app_client):
    """Added FD has an id in the response."""
    response = app_client.post(
        "/api/fixed-deposits/add",
        json=FD_PAYLOAD,
        headers=HEADERS,
    )
    data = response.json()
    assert "id" in data
    assert data["id"]


def test_add_fd_response_has_bank(app_client):
    """Added FD response contains bank name."""
    response = app_client.post(
        "/api/fixed-deposits/add",
        json=FD_PAYLOAD,
        headers=HEADERS,
    )
    data = response.json()
    assert data.get("bank") == "SBI"


def test_add_fd_missing_bank_returns_422(app_client):
    """POST /api/fixed-deposits/add without bank returns 422."""
    payload = {k: v for k, v in FD_PAYLOAD.items() if k != "bank"}
    response = app_client.post(
        "/api/fixed-deposits/add",
        json=payload,
        headers=HEADERS,
    )
    assert response.status_code == 422


def test_add_fd_missing_principal_returns_422(app_client):
    """POST /api/fixed-deposits/add without principal returns 422."""
    payload = {k: v for k, v in FD_PAYLOAD.items() if k != "principal"}
    response = app_client.post(
        "/api/fixed-deposits/add",
        json=payload,
        headers=HEADERS,
    )
    assert response.status_code == 422


def test_add_fd_appears_in_summary(app_client):
    """After adding, FD appears in summary."""
    app_client.post(
        "/api/fixed-deposits/add",
        json={**FD_PAYLOAD, "bank": "HDFC"},
        headers=HEADERS,
    )
    response = app_client.get("/api/fixed-deposits/summary", headers=HEADERS)
    data = response.json()
    banks = [fd.get("bank") for fd in data]
    assert "HDFC" in banks


# ── PUT /api/fixed-deposits/{id} ────────────────────────────────────────────

def test_update_fd_not_found_returns_404(app_client):
    """PUT /api/fixed-deposits/{id} with unknown id returns 404."""
    response = app_client.put(
        "/api/fixed-deposits/nonexistent-id",
        json={"status": "Matured"},
        headers=HEADERS,
    )
    assert response.status_code == 404


def test_update_fd_success(app_client, tmp_dumps_dir):
    """PUT /api/fixed-deposits/{id} updates a JSON-stored FD.
    
    fd_database.update() reads from fixed_deposits.json (not xlsx),
    so we pre-populate that JSON file directly.
    """
    fd_name = "SBI FD 100000"
    fd_id = hashlib.md5(fd_name.encode()).hexdigest()[:8]
    fd_entry = {
        "id": fd_id,
        "name": fd_name,
        "bank": "SBI",
        "principal": 100000.0,
        "interest_rate": 7.5,
        "tenure_months": 12,
        "type": "FD",
        "interest_payout": "Quarterly",
        "start_date": "2024-01-01",
        "maturity_date": "2025-01-01",
        "tds": 0.0,
        "status": "Active",
        "remarks": "",
    }
    json_path = tmp_dumps_dir / "test@example.com" / "TestUser" / "fixed_deposits.json"
    json_path.write_text(json.dumps([fd_entry]))

    update_resp = app_client.put(
        f"/api/fixed-deposits/{fd_id}",
        json={"status": "Matured", "remarks": "Matured on time"},
        headers=HEADERS,
    )
    assert update_resp.status_code == 200
    data = update_resp.json()
    assert data.get("status") == "Matured"


# ── DELETE /api/fixed-deposits/{id} ─────────────────────────────────────────

def test_delete_fd_not_found_returns_404(app_client):
    """DELETE /api/fixed-deposits/{id} with unknown id returns 404."""
    response = app_client.delete("/api/fixed-deposits/nonexistent-id", headers=HEADERS)
    assert response.status_code == 404


def test_delete_fd_success(app_client):
    """DELETE /api/fixed-deposits/{id} removes an xlsx-stored FD.
    
    fd_database.delete() first tries to find/delete an xlsx file by matching
    _gen_fd_id(filename_stem) == fd_id, then falls back to JSON.
    """
    add_resp = app_client.post(
        "/api/fixed-deposits/add",
        json={**FD_PAYLOAD, "bank": "Axis"},
        headers=HEADERS,
    )
    fd_id = add_resp.json()["id"]

    del_resp = app_client.delete(f"/api/fixed-deposits/{fd_id}", headers=HEADERS)
    assert del_resp.status_code == 200


def test_deleted_fd_not_in_summary(app_client):
    """Deleted FD no longer appears in summary."""
    add_resp = app_client.post(
        "/api/fixed-deposits/add",
        json={**FD_PAYLOAD, "bank": "Kotak"},
        headers=HEADERS,
    )
    fd_id = add_resp.json()["id"]

    app_client.delete(f"/api/fixed-deposits/{fd_id}", headers=HEADERS)

    summary = app_client.get("/api/fixed-deposits/summary", headers=HEADERS).json()
    ids = [fd["id"] for fd in summary]
    assert fd_id not in ids
