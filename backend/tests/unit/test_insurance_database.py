"""Unit tests for app/insurance_database.py — Insurance database layer."""
import json
from pathlib import Path
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def ins_base_dir(tmp_path):
    """Create a temp base dir for insurance JSON file."""
    return tmp_path


@pytest.fixture(autouse=True)
def _mock_drive():
    with patch("app.insurance_database._sync_to_drive"), \
         patch("app.insurance_database._delete_from_drive"):
        yield


# ---------------------------------------------------------------------------
# Tests — empty state
# ---------------------------------------------------------------------------

def test_get_all_empty(ins_base_dir):
    from app.insurance_database import get_all
    assert get_all(base_dir=str(ins_base_dir)) == []


def test_get_dashboard_empty(ins_base_dir):
    from app.insurance_database import get_dashboard
    dash = get_dashboard(base_dir=str(ins_base_dir))
    assert dash["active_count"] == 0
    assert dash["total_count"] == 0
    assert dash["total_annual_premium"] == 0
    assert dash["total_coverage"] == 0


# ---------------------------------------------------------------------------
# Tests — add
# ---------------------------------------------------------------------------

def test_add_policy(ins_base_dir):
    from app.insurance_database import add, get_all
    data = {
        "policy_name": "Star Health",
        "provider": "Star Health Insurance",
        "type": "Health",
        "policy_number": "POL123",
        "premium": 25000,
        "coverage_amount": 1000000,
        "start_date": "2024-01-01",
        "expiry_date": "2025-01-01",
        "payment_frequency": "Annual",
        "status": "Active",
    }
    result = add(data, base_dir=str(ins_base_dir))
    assert result["policy_name"] == "Star Health"
    assert result["premium"] == 25000
    assert result["id"]

    # Persisted in JSON
    items = get_all(base_dir=str(ins_base_dir))
    assert len(items) == 1
    assert items[0]["policy_name"] == "Star Health"


def test_add_monthly_premium(ins_base_dir):
    from app.insurance_database import add, get_all
    add({
        "policy_name": "Car Insurance",
        "provider": "ICICI Lombard",
        "type": "Car",
        "premium": 2000,
        "coverage_amount": 500000,
        "start_date": "2024-06-01",
        "expiry_date": "2025-06-01",
        "payment_frequency": "Monthly",
    }, base_dir=str(ins_base_dir))

    items = get_all(base_dir=str(ins_base_dir))
    assert len(items) == 1
    # Annual premium = 2000 * 12 = 24000
    assert items[0]["annual_premium"] == 24000


def test_add_quarterly_premium(ins_base_dir):
    from app.insurance_database import add, get_all
    add({
        "policy_name": "Life Cover",
        "provider": "LIC",
        "premium": 10000,
        "start_date": "2024-01-01",
        "expiry_date": "2030-01-01",
        "payment_frequency": "Quarterly",
    }, base_dir=str(ins_base_dir))

    items = get_all(base_dir=str(ins_base_dir))
    # Annual premium = 10000 * 4 = 40000
    assert items[0]["annual_premium"] == 40000


# ---------------------------------------------------------------------------
# Tests — update
# ---------------------------------------------------------------------------

def test_update_policy(ins_base_dir):
    from app.insurance_database import add, update
    result = add({
        "policy_name": "Bike Insurance",
        "provider": "Bajaj",
        "premium": 3000,
        "start_date": "2024-01-01",
        "expiry_date": "2025-01-01",
    }, base_dir=str(ins_base_dir))
    pol_id = result["id"]

    updated = update(pol_id, {"premium": 3500, "remarks": "Renewed"}, base_dir=str(ins_base_dir))
    assert updated["premium"] == 3500
    assert updated["remarks"] == "Renewed"


def test_update_nonexistent_raises(ins_base_dir):
    from app.insurance_database import update
    with pytest.raises(ValueError, match="not found"):
        update("bad_id", {"premium": 0}, base_dir=str(ins_base_dir))


# ---------------------------------------------------------------------------
# Tests — delete
# ---------------------------------------------------------------------------

def test_delete_policy(ins_base_dir):
    from app.insurance_database import add, delete, get_all
    result = add({
        "policy_name": "Delete Me",
        "provider": "Test",
        "premium": 1000,
        "start_date": "2024-01-01",
        "expiry_date": "2025-01-01",
    }, base_dir=str(ins_base_dir))
    pol_id = result["id"]

    items = get_all(base_dir=str(ins_base_dir))
    assert len(items) == 1

    del_result = delete(pol_id, base_dir=str(ins_base_dir))
    assert "deleted" in del_result["message"]

    items = get_all(base_dir=str(ins_base_dir))
    assert len(items) == 0


def test_delete_nonexistent_raises(ins_base_dir):
    from app.insurance_database import delete
    with pytest.raises(ValueError, match="not found"):
        delete("bad_id", base_dir=str(ins_base_dir))


# ---------------------------------------------------------------------------
# Tests — dashboard
# ---------------------------------------------------------------------------

def test_dashboard_aggregation(ins_base_dir):
    from app.insurance_database import add, get_dashboard
    add({
        "policy_name": "Health 1",
        "provider": "Star",
        "premium": 20000,
        "coverage_amount": 1000000,
        "start_date": "2024-01-01",
        "expiry_date": "2027-01-01",
        "payment_frequency": "Annual",
        "status": "Active",
    }, base_dir=str(ins_base_dir))
    add({
        "policy_name": "Life 1",
        "provider": "LIC",
        "premium": 50000,
        "coverage_amount": 5000000,
        "start_date": "2024-01-01",
        "expiry_date": "2040-01-01",
        "payment_frequency": "Annual",
        "status": "Active",
    }, base_dir=str(ins_base_dir))

    dash = get_dashboard(base_dir=str(ins_base_dir))
    assert dash["active_count"] == 2
    assert dash["total_count"] == 2
    assert dash["total_annual_premium"] == 70000
    assert dash["total_coverage"] == 6000000


# ---------------------------------------------------------------------------
# Tests — days_to_expiry
# ---------------------------------------------------------------------------

def test_days_to_expiry_computed(ins_base_dir):
    from app.insurance_database import add, get_all
    add({
        "policy_name": "Future Policy",
        "provider": "Test",
        "premium": 5000,
        "start_date": "2024-01-01",
        "expiry_date": "2030-12-31",
    }, base_dir=str(ins_base_dir))

    items = get_all(base_dir=str(ins_base_dir))
    assert items[0]["days_to_expiry"] > 0


def test_days_to_expiry_past(ins_base_dir):
    from app.insurance_database import add, get_all
    add({
        "policy_name": "Expired Policy",
        "provider": "Test",
        "premium": 5000,
        "start_date": "2020-01-01",
        "expiry_date": "2021-01-01",
    }, base_dir=str(ins_base_dir))

    items = get_all(base_dir=str(ins_base_dir))
    # Past expiry gives negative days
    assert items[0]["days_to_expiry"] < 0


# ---------------------------------------------------------------------------
# Tests — _sync_to_drive / _delete_from_drive (no-ops, cover lines 28, 33-45)
# ---------------------------------------------------------------------------

def test_sync_to_drive_is_noop():
    """_sync_to_drive is a no-op that should not raise."""
    from app.insurance_database import _sync_to_drive
    from pathlib import Path
    _sync_to_drive(Path("/tmp/test.json"))  # should not raise


def test_delete_from_drive_handles_exception():
    """_delete_from_drive swallows exceptions from drive_service."""
    from app.insurance_database import _delete_from_drive
    from pathlib import Path
    # Calling with a path that won't resolve relative to DUMPS_BASE
    # should not raise — exception is caught
    _delete_from_drive(Path("/nonexistent/path/file.json"))


# ---------------------------------------------------------------------------
# Tests — days_to_expiry invalid date (covers line 82-83)
# ---------------------------------------------------------------------------

def test_days_to_expiry_invalid_date(ins_base_dir):
    """When expiry_date is invalid, days_to_expiry defaults to 0."""
    from app.insurance_database import _load, _save
    json_file = ins_base_dir / "insurance_policies.json"
    # Write a policy with an invalid expiry_date directly
    _save([{
        "id": "inv001",
        "policy_name": "Bad Date",
        "provider": "Test",
        "premium": 1000,
        "coverage_amount": 100000,
        "start_date": "2024-01-01",
        "expiry_date": "not-a-date",
        "payment_frequency": "Annual",
        "status": "Active",
        "remarks": "",
    }], json_file)

    from app.insurance_database import get_all
    items = get_all(base_dir=str(ins_base_dir))
    assert len(items) == 1
    assert items[0]["days_to_expiry"] == 0


# ---------------------------------------------------------------------------
# Tests — dashboard with expiring soon (covers line 101)
# ---------------------------------------------------------------------------

def test_dashboard_expiring_soon(ins_base_dir):
    """Verify expiring_soon count when policy expires within 90 days."""
    from app.insurance_database import _save, get_dashboard
    from datetime import datetime, timedelta
    json_file = ins_base_dir / "insurance_policies.json"
    soon = (datetime.now().date() + timedelta(days=30)).strftime("%Y-%m-%d")
    _save([{
        "id": "soon001",
        "policy_name": "Expiring Soon",
        "provider": "Test",
        "premium": 5000,
        "coverage_amount": 100000,
        "start_date": "2020-01-01",
        "expiry_date": soon,
        "payment_frequency": "Annual",
        "status": "Active",
        "remarks": "",
    }], json_file)

    dash = get_dashboard(base_dir=str(ins_base_dir))
    assert dash["expiring_soon"] == 1
