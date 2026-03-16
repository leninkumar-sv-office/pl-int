"""Unit tests for app/rd_database.py — Recurring Deposit database layer."""
import json
from pathlib import Path
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def rd_base_dir(tmp_path):
    """Create a temp base dir with RD subdir."""
    (tmp_path / "RD").mkdir()
    return tmp_path


@pytest.fixture(autouse=True)
def _mock_drive():
    with patch("app.rd_database._sync_to_drive"), \
         patch("app.rd_database._delete_from_drive"):
        yield


# ---------------------------------------------------------------------------
# Tests — empty state
# ---------------------------------------------------------------------------

def test_get_all_empty(rd_base_dir):
    from app.rd_database import get_all
    assert get_all(base_dir=str(rd_base_dir)) == []


def test_get_dashboard_empty(rd_base_dir):
    from app.rd_database import get_dashboard
    dash = get_dashboard(base_dir=str(rd_base_dir))
    assert dash["active_count"] == 0
    assert dash["total_count"] == 0
    assert dash["total_deposited"] == 0


# ---------------------------------------------------------------------------
# Tests — add
# ---------------------------------------------------------------------------

def test_add_creates_xlsx(rd_base_dir):
    from app.rd_database import add, get_all
    data = {
        "bank": "Post Office",
        "monthly_amount": 5000,
        "interest_rate": 6.7,
        "tenure_months": 60,
        "start_date": "2024-01-01",
        "compounding_frequency": 4,
    }
    result = add(data, base_dir=str(rd_base_dir))
    assert result["bank"] == "Post Office"
    assert result["monthly_amount"] == 5000
    assert result["interest_rate"] == 6.7
    assert result["maturity_amount"] > 5000 * 60  # principal + interest

    # xlsx created
    xlsx_files = list((rd_base_dir / "RD").glob("*.xlsx"))
    assert len(xlsx_files) == 1

    # get_all picks it up
    items = get_all(base_dir=str(rd_base_dir))
    assert len(items) == 1
    assert items[0]["source"] == "xlsx"


def test_add_with_account_number(rd_base_dir):
    from app.rd_database import add
    data = {
        "bank": "SBI",
        "monthly_amount": 10000,
        "interest_rate": 6.5,
        "tenure_months": 24,
        "start_date": "2024-06-01",
        "account_number": "123456789012",
    }
    result = add(data, base_dir=str(rd_base_dir))
    assert "123456789012" in result["name"]


# ---------------------------------------------------------------------------
# Tests — compound interest calculation
# ---------------------------------------------------------------------------

def test_compute_rd_installments_quarterly():
    from app.rd_database import _compute_rd_installments
    installments = _compute_rd_installments(
        monthly_amount=5000, rate_pct=6.0, tenure_months=12,
        start_date="2020-01-01", frequency=4
    )
    assert len(installments) == 12
    # Compound months: 4, 8, 12
    compound_months = [i for i in installments if i["is_compound_month"]]
    assert len(compound_months) == 3
    # First compound at month 4: (5000 * 4 + 0) * 0.06 * 4 / 12 = 20000 * 0.02 = 400
    # All past (2020), so interest_earned should be set
    assert compound_months[0]["interest_earned"] == 400.0


def test_compute_rd_installments_monthly():
    from app.rd_database import _compute_rd_installments
    installments = _compute_rd_installments(
        monthly_amount=1000, rate_pct=12.0, tenure_months=4,
        start_date="2020-01-01", frequency=1
    )
    assert len(installments) == 4
    # Monthly compound: every month is compound
    # Month 1: (1000*1 + 0) * 0.12 * 1/12 = 1000 * 0.01 = 10
    assert installments[0]["is_compound_month"]
    assert installments[0]["interest_earned"] == 10.0


# ---------------------------------------------------------------------------
# Tests — maturity date
# ---------------------------------------------------------------------------

def test_calc_maturity_date():
    from app.rd_database import _calc_maturity_date
    assert _calc_maturity_date("2024-01-15", 60) == "2029-01-15"
    assert _calc_maturity_date("2024-03-01", 12) == "2025-03-01"


# ---------------------------------------------------------------------------
# Tests — delete
# ---------------------------------------------------------------------------

def test_delete_xlsx_rd(rd_base_dir):
    from app.rd_database import add, delete, get_all
    data = {
        "bank": "PO",
        "monthly_amount": 5000,
        "interest_rate": 6.7,
        "tenure_months": 60,
        "start_date": "2024-01-01",
    }
    result = add(data, base_dir=str(rd_base_dir))
    rd_id = result["id"]

    items = get_all(base_dir=str(rd_base_dir))
    assert len(items) == 1

    del_result = delete(rd_id, base_dir=str(rd_base_dir))
    assert "deleted" in del_result["message"]

    items = get_all(base_dir=str(rd_base_dir))
    assert len(items) == 0


def test_delete_nonexistent_raises(rd_base_dir):
    from app.rd_database import delete
    with pytest.raises(ValueError, match="not found"):
        delete("bad_id", base_dir=str(rd_base_dir))


# ---------------------------------------------------------------------------
# Tests — update JSON entry
# ---------------------------------------------------------------------------

def test_update_json_entry(rd_base_dir):
    from app.rd_database import _save_json, update
    json_file = rd_base_dir / "recurring_deposits.json"
    entry = {
        "id": "rd001",
        "bank": "HDFC",
        "monthly_amount": 5000,
        "interest_rate": 7.0,
        "tenure_months": 60,
        "start_date": "2023-01-01",
        "maturity_date": "2028-01-01",
        "compounding_frequency": 4,
        "status": "Active",
        "remarks": "",
        "name": "HDFC RD",
    }
    _save_json([entry], json_file=json_file, dumps_dir=rd_base_dir)

    result = update("rd001", {"monthly_amount": 10000}, base_dir=str(rd_base_dir))
    assert result["monthly_amount"] == 10000
    assert result["maturity_amount"] > 10000 * 60


def test_update_nonexistent_raises(rd_base_dir):
    from app.rd_database import update
    json_file = rd_base_dir / "recurring_deposits.json"
    json_file.write_text("[]")
    with pytest.raises(ValueError, match="not found"):
        update("nope", {"bank": "X"}, base_dir=str(rd_base_dir))


# ---------------------------------------------------------------------------
# Tests — add_installment
# ---------------------------------------------------------------------------

def test_add_installment_to_json_rd(rd_base_dir):
    from app.rd_database import _save_json, add_installment
    json_file = rd_base_dir / "recurring_deposits.json"
    entry = {
        "id": "rd002",
        "bank": "SBI",
        "monthly_amount": 5000,
        "interest_rate": 6.5,
        "tenure_months": 60,
        "start_date": "2023-06-01",
        "maturity_date": "2028-06-01",
        "compounding_frequency": 4,
        "status": "Active",
        "remarks": "",
        "name": "SBI RD",
    }
    _save_json([entry], json_file=json_file, dumps_dir=rd_base_dir)

    result = add_installment("rd002", {
        "date": "2024-01-01",
        "amount": 5000,
        "remarks": "extra",
    }, base_dir=str(rd_base_dir))
    assert len(result["extra_installments"]) == 1
    assert result["extra_installments"][0]["amount"] == 5000


# ---------------------------------------------------------------------------
# Tests — dashboard
# ---------------------------------------------------------------------------

def test_dashboard_after_add(rd_base_dir):
    from app.rd_database import add, get_dashboard
    add({
        "bank": "PO",
        "monthly_amount": 5000,
        "interest_rate": 6.7,
        "tenure_months": 60,
        "start_date": "2025-01-01",
    }, base_dir=str(rd_base_dir))

    dash = get_dashboard(base_dir=str(rd_base_dir))
    assert dash["total_count"] == 1
    assert dash["active_count"] == 1
    assert dash["monthly_commitment"] == 5000


# ---------------------------------------------------------------------------
# Tests — helper: extract_account_number
# ---------------------------------------------------------------------------

def test_extract_account_number():
    from app.rd_database import _extract_account_number
    assert _extract_account_number("Post Office RD - 020123343379") == "020123343379"
    assert _extract_account_number("SBI RD") == ""


# ---------------------------------------------------------------------------
# Tests — gen_rd_id determinism
# ---------------------------------------------------------------------------

def test_gen_rd_id_deterministic():
    from app.rd_database import _gen_rd_id
    assert _gen_rd_id("PO RD") == _gen_rd_id("PO RD")
    assert _gen_rd_id("PO RD") != _gen_rd_id("SBI RD")
