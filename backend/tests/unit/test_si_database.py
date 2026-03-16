"""Unit tests for app/si_database.py — Standing Instructions database layer."""
import json
from pathlib import Path
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def si_base_dir(tmp_path):
    """Create a temp base dir with Standing Instructions subdir."""
    (tmp_path / "Standing Instructions").mkdir()
    return tmp_path


@pytest.fixture(autouse=True)
def _mock_drive():
    with patch("app.si_database._sync_to_drive"), \
         patch("app.si_database._delete_from_drive"):
        yield


# ---------------------------------------------------------------------------
# Tests — empty state
# ---------------------------------------------------------------------------

def test_get_all_empty(si_base_dir):
    from app.si_database import get_all
    assert get_all(base_dir=str(si_base_dir)) == []


def test_get_dashboard_empty(si_base_dir):
    from app.si_database import get_dashboard
    dash = get_dashboard(base_dir=str(si_base_dir))
    assert dash["active_count"] == 0
    assert dash["total_count"] == 0
    assert dash["total_monthly_outflow"] == 0


# ---------------------------------------------------------------------------
# Tests — add
# ---------------------------------------------------------------------------

def test_add_si(si_base_dir):
    from app.si_database import add, get_all
    data = {
        "bank": "HDFC",
        "beneficiary": "Mutual Fund X",
        "amount": 5000,
        "frequency": "Monthly",
        "purpose": "SIP",
        "mandate_type": "NACH",
        "account_number": "1234567890",
        "start_date": "2024-01-01",
        "expiry_date": "2027-01-01",
        "alert_days": 30,
        "status": "Active",
    }
    result = add(data, base_dir=str(si_base_dir))
    assert result["bank"] == "HDFC"
    assert result["beneficiary"] == "Mutual Fund X"
    assert result["amount"] == 5000
    assert result["id"]

    # Persisted
    items = get_all(base_dir=str(si_base_dir))
    assert len(items) == 1
    assert items[0]["bank"] == "HDFC"


def test_add_multiple_sis(si_base_dir):
    from app.si_database import add, get_all
    for i in range(3):
        add({
            "bank": f"Bank{i}",
            "beneficiary": f"Ben{i}",
            "amount": 1000 * (i + 1),
            "start_date": "2024-01-01",
            "expiry_date": "2027-01-01",
        }, base_dir=str(si_base_dir))

    items = get_all(base_dir=str(si_base_dir))
    assert len(items) == 3


# ---------------------------------------------------------------------------
# Tests — update
# ---------------------------------------------------------------------------

def test_update_si(si_base_dir):
    from app.si_database import add, update
    result = add({
        "bank": "SBI",
        "beneficiary": "Insurance Co",
        "amount": 10000,
        "start_date": "2024-01-01",
        "expiry_date": "2025-01-01",
    }, base_dir=str(si_base_dir))
    si_id = result["id"]

    updated = update(si_id, {"amount": 15000, "frequency": "Quarterly"}, base_dir=str(si_base_dir))
    assert updated["amount"] == 15000
    assert updated["frequency"] == "Quarterly"


def test_update_nonexistent_raises(si_base_dir):
    from app.si_database import update
    with pytest.raises(ValueError, match="not found"):
        update("bad", {"amount": 0}, base_dir=str(si_base_dir))


# ---------------------------------------------------------------------------
# Tests — delete
# ---------------------------------------------------------------------------

def test_delete_si(si_base_dir):
    from app.si_database import add, delete, get_all
    result = add({
        "bank": "ICICI",
        "beneficiary": "EMI",
        "amount": 25000,
        "start_date": "2024-01-01",
        "expiry_date": "2026-01-01",
    }, base_dir=str(si_base_dir))
    si_id = result["id"]

    items = get_all(base_dir=str(si_base_dir))
    assert len(items) == 1

    del_result = delete(si_id, base_dir=str(si_base_dir))
    assert "deleted" in del_result["message"]

    items = get_all(base_dir=str(si_base_dir))
    assert len(items) == 0


def test_delete_nonexistent_raises(si_base_dir):
    from app.si_database import delete
    with pytest.raises(ValueError, match="not found"):
        delete("bad", base_dir=str(si_base_dir))


# ---------------------------------------------------------------------------
# Tests — dashboard
# ---------------------------------------------------------------------------

def test_dashboard_monthly_outflow(si_base_dir):
    from app.si_database import add, get_dashboard
    # Add a monthly SI
    add({
        "bank": "HDFC",
        "beneficiary": "MF",
        "amount": 5000,
        "frequency": "Monthly",
        "start_date": "2024-01-01",
        "expiry_date": "2027-01-01",
    }, base_dir=str(si_base_dir))
    # Add a quarterly SI
    add({
        "bank": "SBI",
        "beneficiary": "Insurance",
        "amount": 12000,
        "frequency": "Quarterly",
        "start_date": "2024-01-01",
        "expiry_date": "2027-01-01",
    }, base_dir=str(si_base_dir))

    dash = get_dashboard(base_dir=str(si_base_dir))
    assert dash["active_count"] == 2
    assert dash["total_count"] == 2
    # Monthly: 5000; Quarterly 12000/3 = 4000; total = 9000
    assert dash["total_monthly_outflow"] == 9000.0


# ---------------------------------------------------------------------------
# Tests — days_to_expiry computed field
# ---------------------------------------------------------------------------

def test_days_to_expiry_computed(si_base_dir):
    from app.si_database import add, get_all
    result = add({
        "bank": "BOB",
        "beneficiary": "Utility",
        "amount": 500,
        "start_date": "2020-01-01",
        "expiry_date": "2030-12-31",
    }, base_dir=str(si_base_dir))

    items = get_all(base_dir=str(si_base_dir))
    assert len(items) == 1
    # Expiry is far in the future, so days_to_expiry should be positive
    assert items[0]["days_to_expiry"] > 0


# ---------------------------------------------------------------------------
# Tests — _to_date_str helper
# ---------------------------------------------------------------------------

def test_to_date_str():
    from app.si_database import _to_date_str
    from datetime import datetime, date
    assert _to_date_str(datetime(2024, 6, 15)) == "2024-06-15"
    assert _to_date_str(date(2024, 6, 15)) == "2024-06-15"
    assert _to_date_str("2024-06-15") == "2024-06-15"
    assert _to_date_str(None) == ""
    assert _to_date_str("") == ""
