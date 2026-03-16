"""Integration tests for PPF, NPS, Standing Instructions, and Insurance endpoints."""

import pytest

HEADERS = {"X-User-Id": "testuser"}


# ════════════════════════════════════════════════════════════
#  PPF
# ════════════════════════════════════════════════════════════

PPF_PAYLOAD = {
    "bank": "SBI",
    "start_date": "2020-04-01",
    "account_name": "My PPF Account",
    "interest_rate": 7.1,
}


def test_ppf_summary_returns_200(app_client):
    response = app_client.get("/api/ppf/summary", headers=HEADERS)
    assert response.status_code == 200


def test_ppf_summary_empty(app_client):
    response = app_client.get("/api/ppf/summary", headers=HEADERS)
    assert isinstance(response.json(), list)


def test_ppf_dashboard_returns_200(app_client):
    response = app_client.get("/api/ppf/dashboard", headers=HEADERS)
    assert response.status_code == 200


def test_add_ppf_returns_200(app_client):
    response = app_client.post("/api/ppf/add", json=PPF_PAYLOAD, headers=HEADERS)
    assert response.status_code == 200


def test_add_ppf_has_id(app_client):
    response = app_client.post("/api/ppf/add", json=PPF_PAYLOAD, headers=HEADERS)
    assert "id" in response.json()


def test_add_ppf_missing_bank_returns_422(app_client):
    payload = {k: v for k, v in PPF_PAYLOAD.items() if k != "bank"}
    response = app_client.post("/api/ppf/add", json=payload, headers=HEADERS)
    assert response.status_code == 422


def test_update_ppf_not_found_returns_404(app_client):
    response = app_client.put("/api/ppf/nonexistent", json={"interest_rate": 7.5}, headers=HEADERS)
    assert response.status_code == 404


def test_update_ppf_success(app_client):
    add_resp = app_client.post("/api/ppf/add", json=PPF_PAYLOAD, headers=HEADERS)
    ppf_id = add_resp.json()["id"]

    update_resp = app_client.put(
        f"/api/ppf/{ppf_id}",
        json={"interest_rate": 7.5, "remarks": "Rate updated"},
        headers=HEADERS,
    )
    assert update_resp.status_code == 200


def test_delete_ppf_not_found_returns_404(app_client):
    response = app_client.delete("/api/ppf/nonexistent", headers=HEADERS)
    assert response.status_code == 404


def test_delete_ppf_success(app_client):
    add_resp = app_client.post("/api/ppf/add", json=PPF_PAYLOAD, headers=HEADERS)
    ppf_id = add_resp.json()["id"]
    del_resp = app_client.delete(f"/api/ppf/{ppf_id}", headers=HEADERS)
    assert del_resp.status_code == 200


def test_add_ppf_contribution_not_found_returns_400(app_client):
    """Contribution on a non-existent PPF account returns 400 or 404."""
    response = app_client.post(
        "/api/ppf/nonexistent/contribution",
        json={"date": "2024-04-01", "amount": 10000.0},
        headers=HEADERS,
    )
    assert response.status_code in (400, 404)


def test_add_ppf_contribution_success(app_client):
    add_resp = app_client.post("/api/ppf/add", json=PPF_PAYLOAD, headers=HEADERS)
    ppf_id = add_resp.json()["id"]

    contrib_resp = app_client.post(
        f"/api/ppf/{ppf_id}/contribution",
        json={"date": "2024-04-01", "amount": 10000.0, "remarks": "Annual contribution"},
        headers=HEADERS,
    )
    assert contrib_resp.status_code == 200


def test_add_ppf_contribution_missing_date_returns_422(app_client):
    add_resp = app_client.post("/api/ppf/add", json=PPF_PAYLOAD, headers=HEADERS)
    ppf_id = add_resp.json()["id"]

    response = app_client.post(
        f"/api/ppf/{ppf_id}/contribution",
        json={"amount": 10000.0},
        headers=HEADERS,
    )
    assert response.status_code == 422


# ════════════════════════════════════════════════════════════
#  NPS
# ════════════════════════════════════════════════════════════

NPS_PAYLOAD = {
    "start_date": "2020-01-01",
    "account_name": "My NPS Account",
    "tier": "Tier I",
    "fund_manager": "SBI Pension Funds",
}


def _get_nps_id_after_add(client, add_resp):
    """Get the stable NPS ID by reading from summary after add.
    NPS IDs are regenerated from PRAN/filename when reading back from xlsx,
    so the id in add response may differ from the stored id.
    """
    nps_id_from_add = add_resp.json().get("id")
    # Re-read from summary to get the stable ID
    summary = client.get("/api/nps/summary", headers=HEADERS).json()
    if summary:
        return summary[-1]["id"]  # Latest added is last
    return nps_id_from_add


def test_nps_summary_returns_200(app_client):
    response = app_client.get("/api/nps/summary", headers=HEADERS)
    assert response.status_code == 200


def test_nps_summary_empty(app_client):
    response = app_client.get("/api/nps/summary", headers=HEADERS)
    assert isinstance(response.json(), list)


def test_nps_dashboard_returns_200(app_client):
    response = app_client.get("/api/nps/dashboard", headers=HEADERS)
    assert response.status_code == 200


def test_add_nps_returns_200(app_client):
    response = app_client.post("/api/nps/add", json=NPS_PAYLOAD, headers=HEADERS)
    assert response.status_code == 200


def test_add_nps_has_id(app_client):
    response = app_client.post("/api/nps/add", json=NPS_PAYLOAD, headers=HEADERS)
    assert "id" in response.json()


def test_add_nps_missing_start_date_returns_422(app_client):
    payload = {k: v for k, v in NPS_PAYLOAD.items() if k != "start_date"}
    response = app_client.post("/api/nps/add", json=payload, headers=HEADERS)
    assert response.status_code == 422


def test_update_nps_not_found_returns_404(app_client):
    response = app_client.put("/api/nps/nonexistent", json={"current_value": 100000.0}, headers=HEADERS)
    assert response.status_code == 404


def test_update_nps_success(app_client):
    add_resp = app_client.post("/api/nps/add", json=NPS_PAYLOAD, headers=HEADERS)
    nps_id = _get_nps_id_after_add(app_client, add_resp)

    update_resp = app_client.put(
        f"/api/nps/{nps_id}",
        json={"current_value": 150000.0},
        headers=HEADERS,
    )
    assert update_resp.status_code == 200


def test_delete_nps_not_found_returns_404(app_client):
    response = app_client.delete("/api/nps/nonexistent", headers=HEADERS)
    assert response.status_code == 404


def test_delete_nps_success(app_client):
    add_resp = app_client.post("/api/nps/add", json=NPS_PAYLOAD, headers=HEADERS)
    nps_id = _get_nps_id_after_add(app_client, add_resp)
    del_resp = app_client.delete(f"/api/nps/{nps_id}", headers=HEADERS)
    assert del_resp.status_code == 200


def test_add_nps_contribution_success(app_client):
    add_resp = app_client.post("/api/nps/add", json=NPS_PAYLOAD, headers=HEADERS)
    nps_id = _get_nps_id_after_add(app_client, add_resp)

    contrib_resp = app_client.post(
        f"/api/nps/{nps_id}/contribution",
        json={"date": "2024-03-15", "amount": 5000.0, "remarks": "Monthly contribution"},
        headers=HEADERS,
    )
    assert contrib_resp.status_code == 200


def test_add_nps_contribution_missing_date_returns_422(app_client):
    add_resp = app_client.post("/api/nps/add", json=NPS_PAYLOAD, headers=HEADERS)
    nps_id = _get_nps_id_after_add(app_client, add_resp)

    response = app_client.post(
        f"/api/nps/{nps_id}/contribution",
        json={"amount": 5000.0},
        headers=HEADERS,
    )
    assert response.status_code == 422


# ════════════════════════════════════════════════════════════
#  STANDING INSTRUCTIONS
# ════════════════════════════════════════════════════════════

SI_PAYLOAD = {
    "bank": "HDFC Bank",
    "beneficiary": "Axis Mutual Fund",
    "amount": 5000.0,
    "frequency": "Monthly",
    "start_date": "2024-01-01",
    "expiry_date": "2029-01-01",
    "purpose": "SIP",
    "mandate_type": "NACH",
}


def test_si_summary_returns_200(app_client):
    response = app_client.get("/api/standing-instructions/summary", headers=HEADERS)
    assert response.status_code == 200


def test_si_summary_empty(app_client):
    response = app_client.get("/api/standing-instructions/summary", headers=HEADERS)
    assert isinstance(response.json(), list)


def test_si_dashboard_returns_200(app_client):
    response = app_client.get("/api/standing-instructions/dashboard", headers=HEADERS)
    assert response.status_code == 200


def test_add_si_returns_200(app_client):
    response = app_client.post("/api/standing-instructions/add", json=SI_PAYLOAD, headers=HEADERS)
    assert response.status_code == 200


def test_add_si_has_id(app_client):
    response = app_client.post("/api/standing-instructions/add", json=SI_PAYLOAD, headers=HEADERS)
    assert "id" in response.json()


def test_add_si_missing_bank_returns_422(app_client):
    payload = {k: v for k, v in SI_PAYLOAD.items() if k != "bank"}
    response = app_client.post("/api/standing-instructions/add", json=payload, headers=HEADERS)
    assert response.status_code == 422


def test_update_si_not_found_returns_404(app_client):
    response = app_client.put(
        "/api/standing-instructions/nonexistent",
        json={"status": "Cancelled"},
        headers=HEADERS,
    )
    assert response.status_code == 404


def test_update_si_success(app_client):
    add_resp = app_client.post("/api/standing-instructions/add", json=SI_PAYLOAD, headers=HEADERS)
    si_id = add_resp.json()["id"]

    update_resp = app_client.put(
        f"/api/standing-instructions/{si_id}",
        json={"status": "Cancelled"},
        headers=HEADERS,
    )
    assert update_resp.status_code == 200


def test_delete_si_not_found_returns_404(app_client):
    response = app_client.delete("/api/standing-instructions/nonexistent", headers=HEADERS)
    assert response.status_code == 404


def test_delete_si_success(app_client):
    add_resp = app_client.post("/api/standing-instructions/add", json=SI_PAYLOAD, headers=HEADERS)
    si_id = add_resp.json()["id"]
    del_resp = app_client.delete(f"/api/standing-instructions/{si_id}", headers=HEADERS)
    assert del_resp.status_code == 200


# ════════════════════════════════════════════════════════════
#  INSURANCE
# ════════════════════════════════════════════════════════════

INS_PAYLOAD = {
    "policy_name": "Star Health Family Floater",
    "provider": "Star Health",
    "type": "Health",
    "premium": 25000.0,
    "coverage_amount": 1000000.0,
    "start_date": "2024-04-01",
    "expiry_date": "2025-03-31",
    "payment_frequency": "Annual",
    "status": "Active",
}


def test_insurance_summary_returns_200(app_client):
    response = app_client.get("/api/insurance/summary", headers=HEADERS)
    assert response.status_code == 200


def test_insurance_summary_empty(app_client):
    response = app_client.get("/api/insurance/summary", headers=HEADERS)
    assert isinstance(response.json(), list)


def test_insurance_dashboard_returns_200(app_client):
    response = app_client.get("/api/insurance/dashboard", headers=HEADERS)
    assert response.status_code == 200


def test_add_insurance_returns_200(app_client):
    response = app_client.post("/api/insurance/add", json=INS_PAYLOAD, headers=HEADERS)
    assert response.status_code == 200


def test_add_insurance_has_id(app_client):
    response = app_client.post("/api/insurance/add", json=INS_PAYLOAD, headers=HEADERS)
    assert "id" in response.json()


def test_add_insurance_missing_policy_name_returns_422(app_client):
    payload = {k: v for k, v in INS_PAYLOAD.items() if k != "policy_name"}
    response = app_client.post("/api/insurance/add", json=payload, headers=HEADERS)
    assert response.status_code == 422


def test_add_insurance_missing_provider_returns_422(app_client):
    payload = {k: v for k, v in INS_PAYLOAD.items() if k != "provider"}
    response = app_client.post("/api/insurance/add", json=payload, headers=HEADERS)
    assert response.status_code == 422


def test_update_insurance_not_found_returns_404(app_client):
    response = app_client.put(
        "/api/insurance/nonexistent",
        json={"status": "Expired"},
        headers=HEADERS,
    )
    assert response.status_code == 404


def test_update_insurance_success(app_client):
    add_resp = app_client.post("/api/insurance/add", json=INS_PAYLOAD, headers=HEADERS)
    policy_id = add_resp.json()["id"]

    update_resp = app_client.put(
        f"/api/insurance/{policy_id}",
        json={"status": "Expired", "remarks": "Expired naturally"},
        headers=HEADERS,
    )
    assert update_resp.status_code == 200


def test_delete_insurance_not_found_returns_404(app_client):
    response = app_client.delete("/api/insurance/nonexistent", headers=HEADERS)
    assert response.status_code == 404


def test_delete_insurance_success(app_client):
    add_resp = app_client.post("/api/insurance/add", json=INS_PAYLOAD, headers=HEADERS)
    policy_id = add_resp.json()["id"]
    del_resp = app_client.delete(f"/api/insurance/{policy_id}", headers=HEADERS)
    assert del_resp.status_code == 200
