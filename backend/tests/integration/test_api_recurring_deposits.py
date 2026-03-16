"""Integration tests for Recurring Deposit CRUD endpoints."""

import pytest
import json
import hashlib

HEADERS = {"X-User-Id": "testuser"}

RD_PAYLOAD = {
    "bank": "SBI",
    "monthly_amount": 5000.0,
    "interest_rate": 6.5,
    "tenure_months": 24,
    "start_date": "2024-01-01",
    "maturity_date": "2026-01-01",
    "status": "Active",
}


# ── GET /api/recurring-deposits/summary ─────────────────────────────────────

def test_rd_summary_returns_200(app_client):
    """GET /api/recurring-deposits/summary returns 200."""
    response = app_client.get("/api/recurring-deposits/summary", headers=HEADERS)
    assert response.status_code == 200


def test_rd_summary_empty(app_client):
    """GET /api/recurring-deposits/summary returns empty list initially."""
    response = app_client.get("/api/recurring-deposits/summary", headers=HEADERS)
    data = response.json()
    assert isinstance(data, list)


# ── GET /api/recurring-deposits/dashboard ───────────────────────────────────

def test_rd_dashboard_returns_200(app_client):
    """GET /api/recurring-deposits/dashboard returns 200."""
    response = app_client.get("/api/recurring-deposits/dashboard", headers=HEADERS)
    assert response.status_code == 200


# ── POST /api/recurring-deposits/add ────────────────────────────────────────

def test_add_rd_returns_200(app_client):
    """POST /api/recurring-deposits/add returns 200."""
    response = app_client.post(
        "/api/recurring-deposits/add",
        json=RD_PAYLOAD,
        headers=HEADERS,
    )
    assert response.status_code == 200


def test_add_rd_response_has_id(app_client):
    """Added RD has an id in the response."""
    response = app_client.post(
        "/api/recurring-deposits/add",
        json=RD_PAYLOAD,
        headers=HEADERS,
    )
    data = response.json()
    assert "id" in data
    assert data["id"]


def test_add_rd_missing_bank_returns_422(app_client):
    """POST /api/recurring-deposits/add without bank returns 422."""
    payload = {k: v for k, v in RD_PAYLOAD.items() if k != "bank"}
    response = app_client.post(
        "/api/recurring-deposits/add",
        json=payload,
        headers=HEADERS,
    )
    assert response.status_code == 422


def test_add_rd_missing_monthly_amount_returns_422(app_client):
    """POST /api/recurring-deposits/add without monthly_amount returns 422."""
    payload = {k: v for k, v in RD_PAYLOAD.items() if k != "monthly_amount"}
    response = app_client.post(
        "/api/recurring-deposits/add",
        json=payload,
        headers=HEADERS,
    )
    assert response.status_code == 422


def test_add_rd_appears_in_summary(app_client):
    """After adding, RD appears in summary."""
    app_client.post(
        "/api/recurring-deposits/add",
        json={**RD_PAYLOAD, "bank": "HDFC"},
        headers=HEADERS,
    )
    response = app_client.get("/api/recurring-deposits/summary", headers=HEADERS)
    data = response.json()
    banks = [rd.get("bank") for rd in data]
    assert "HDFC" in banks


# ── PUT /api/recurring-deposits/{id} ────────────────────────────────────────

def test_update_rd_not_found_returns_404(app_client):
    """PUT /api/recurring-deposits/{id} with unknown id returns 404."""
    response = app_client.put(
        "/api/recurring-deposits/nonexistent-id",
        json={"status": "Matured"},
        headers=HEADERS,
    )
    assert response.status_code == 404


def test_update_rd_success(app_client, tmp_dumps_dir):
    """PUT /api/recurring-deposits/{id} updates a JSON-stored RD."""
    # rd_database.update() reads from recurring_deposits.json not xlsx,
    # so we pre-populate the JSON file directly.
    rd_name = "SBI RD Test"
    rd_id = hashlib.md5(rd_name.encode()).hexdigest()[:8]
    rd_entry = {
        "id": rd_id,
        "name": rd_name,
        "bank": "SBI",
        "monthly_amount": 5000.0,
        "interest_rate": 6.5,
        "tenure_months": 24,
        "start_date": "2024-01-01",
        "maturity_date": "2026-01-01",
        "status": "Active",
        "remarks": "",
        "compounding_frequency": 4,
    }
    json_path = tmp_dumps_dir / "test@example.com" / "TestUser" / "recurring_deposits.json"
    json_path.write_text(json.dumps([rd_entry]))

    update_resp = app_client.put(
        f"/api/recurring-deposits/{rd_id}",
        json={"status": "Matured", "remarks": "Done"},
        headers=HEADERS,
    )
    assert update_resp.status_code == 200
    data = update_resp.json()
    assert data.get("status") == "Matured"


# ── DELETE /api/recurring-deposits/{id} ─────────────────────────────────────

def test_delete_rd_not_found_returns_404(app_client):
    """DELETE /api/recurring-deposits/{id} with unknown id returns 404."""
    response = app_client.delete(
        "/api/recurring-deposits/nonexistent-id", headers=HEADERS
    )
    assert response.status_code == 404


def test_delete_rd_success(app_client):
    """DELETE /api/recurring-deposits/{id} removes an xlsx-stored RD."""
    # add() creates an xlsx file; delete() can find it by matching _gen_rd_id(filename_stem)
    add_resp = app_client.post(
        "/api/recurring-deposits/add",
        json={**RD_PAYLOAD, "bank": "Axis"},
        headers=HEADERS,
    )
    rd_id = add_resp.json()["id"]

    del_resp = app_client.delete(f"/api/recurring-deposits/{rd_id}", headers=HEADERS)
    assert del_resp.status_code == 200


# ── POST /api/recurring-deposits/{id}/installment ───────────────────────────

def test_add_installment_not_found_returns_404(app_client):
    """POST installment for non-existent RD returns 404."""
    response = app_client.post(
        "/api/recurring-deposits/nonexistent-id/installment",
        json={"date": "2024-02-01", "amount": 5000.0},
        headers=HEADERS,
    )
    assert response.status_code == 404


def test_add_installment_success(app_client, tmp_dumps_dir):
    """POST installment adds a payment record to a JSON-stored RD."""
    # add_installment() reads from recurring_deposits.json, so pre-populate it
    rd_name = "PNB RD Test"
    rd_id = hashlib.md5(rd_name.encode()).hexdigest()[:8]
    rd_entry = {
        "id": rd_id,
        "name": rd_name,
        "bank": "PNB",
        "monthly_amount": 5000.0,
        "interest_rate": 6.0,
        "tenure_months": 12,
        "start_date": "2024-01-01",
        "maturity_date": "2025-01-01",
        "status": "Active",
        "remarks": "",
        "compounding_frequency": 4,
    }
    json_path = tmp_dumps_dir / "test@example.com" / "TestUser" / "recurring_deposits.json"
    json_path.write_text(json.dumps([rd_entry]))

    inst_resp = app_client.post(
        f"/api/recurring-deposits/{rd_id}/installment",
        json={"date": "2024-02-01", "amount": 5000.0, "remarks": "Feb installment"},
        headers=HEADERS,
    )
    assert inst_resp.status_code == 200


def test_add_installment_missing_date_returns_422(app_client, tmp_dumps_dir):
    """POST installment without date returns 422."""
    rd_name = "Test RD 422"
    rd_id = hashlib.md5(rd_name.encode()).hexdigest()[:8]
    rd_entry = {
        "id": rd_id, "name": rd_name, "bank": "ICICI",
        "monthly_amount": 2000.0, "interest_rate": 6.0, "tenure_months": 12,
        "start_date": "2024-01-01", "maturity_date": "2025-01-01",
        "status": "Active", "remarks": "", "compounding_frequency": 4,
    }
    json_path = tmp_dumps_dir / "test@example.com" / "TestUser" / "recurring_deposits.json"
    json_path.write_text(json.dumps([rd_entry]))

    response = app_client.post(
        f"/api/recurring-deposits/{rd_id}/installment",
        json={"amount": 5000.0},
        headers=HEADERS,
    )
    assert response.status_code == 422
