"""Unit tests for app/fd_database.py — Fixed Deposit database layer."""
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def fd_base_dir(tmp_path):
    """Create a temp base dir with FD subdir and return it."""
    fd_dir = tmp_path / "FD"
    fd_dir.mkdir()
    return tmp_path


@pytest.fixture(autouse=True)
def _mock_drive():
    """Silence all Drive sync/delete calls."""
    with patch("app.fd_database._sync_to_drive"), \
         patch("app.fd_database._delete_from_drive"):
        yield


# ---------------------------------------------------------------------------
# Tests — empty state
# ---------------------------------------------------------------------------

def test_get_all_empty(fd_base_dir):
    from app.fd_database import get_all
    items = get_all(base_dir=str(fd_base_dir))
    assert items == []


def test_get_dashboard_empty(fd_base_dir):
    from app.fd_database import get_dashboard
    dash = get_dashboard(base_dir=str(fd_base_dir))
    assert dash["active_count"] == 0
    assert dash["total_count"] == 0
    assert dash["total_invested"] == 0


# ---------------------------------------------------------------------------
# Tests — add
# ---------------------------------------------------------------------------

def test_add_creates_xlsx_and_returns_item(fd_base_dir):
    from app.fd_database import add, get_all
    data = {
        "bank": "SBI",
        "principal": 100000,
        "interest_rate": 7.0,
        "tenure_months": 12,
        "start_date": "2024-01-01",
        "type": "FD",
        "interest_payout": "Quarterly",
    }
    result = add(data, base_dir=str(fd_base_dir))
    assert result["bank"] == "SBI"
    assert result["principal"] == 100000
    assert result["interest_rate"] == 7.0
    assert result["tenure_months"] == 12
    assert result["maturity_amount"] > 100000
    assert result["id"]

    # Verify xlsx file was created in FD subdir
    fd_dir = fd_base_dir / "FD"
    xlsx_files = list(fd_dir.glob("*.xlsx"))
    assert len(xlsx_files) == 1

    # Verify get_all picks it up
    items = get_all(base_dir=str(fd_base_dir))
    assert len(items) == 1
    assert items[0]["bank"] == "SBI"
    assert items[0]["source"] == "xlsx"


def test_add_mis_type(fd_base_dir):
    from app.fd_database import add
    data = {
        "bank": "Post Office",
        "principal": 500000,
        "interest_rate": 7.4,
        "tenure_months": 60,
        "start_date": "2024-01-01",
        "type": "MIS",
        "name": "PO MIS",
    }
    result = add(data, base_dir=str(fd_base_dir))
    assert result["type"] == "MIS"
    assert result["name"] == "PO MIS"


# ---------------------------------------------------------------------------
# Tests — maturity calculations
# ---------------------------------------------------------------------------

def test_maturity_calculation_quarterly(fd_base_dir):
    from app.fd_database import _calc_maturity
    result = _calc_maturity(100000, 8.0, 12, "Quarterly")
    # 8% annual, quarterly payouts: interest_per_quarter = 100000 * 0.08 / 4 = 2000
    # 12 months = 4 quarters => total interest = 8000
    assert result["interest_earned"] == 8000.0
    assert result["maturity_amount"] == 108000.0


def test_maturity_calculation_monthly(fd_base_dir):
    from app.fd_database import _calc_maturity
    result = _calc_maturity(100000, 6.0, 12, "Monthly")
    # 6% annual, monthly: interest_per_month = 100000 * 0.06 / 12 = 500
    # 12 months, payouts on months 2,3,...,12 that are multiples of 1 => 11 payouts
    # Wait, the formula: m > 1 and m % 1 == 0 => months 2..12 = 11 payouts
    # But _calc_maturity uses: num_periods = tenure_months // period_months = 12 // 1 = 12
    # interest = 500 * 12 = 6000
    assert result["interest_earned"] == 6000.0
    assert result["maturity_amount"] == 106000.0


def test_maturity_calculation_annually(fd_base_dir):
    from app.fd_database import _calc_maturity
    result = _calc_maturity(100000, 10.0, 24, "Annually")
    # 10% annual, yearly payouts: interest_per_year = 100000 * 0.10 / 1 = 10000
    # 24 months = 2 years => num_periods = 24 // 12 = 2
    # total interest = 10000 * 2 = 20000
    assert result["interest_earned"] == 20000.0
    assert result["maturity_amount"] == 120000.0


def test_maturity_date_calculation():
    from app.fd_database import _calc_maturity_date
    result = _calc_maturity_date("2024-01-15", 12)
    assert result == "2025-01-15"

    result = _calc_maturity_date("2024-01-15", 6)
    assert result == "2024-07-15"


# ---------------------------------------------------------------------------
# Tests — installment generation
# ---------------------------------------------------------------------------

def test_generate_installments_length():
    from app.fd_database import _generate_installments
    installments = _generate_installments(100000, 8.0, 12, "2020-01-01", "Quarterly")
    assert len(installments) == 12
    # Month 1 has investment
    assert installments[0]["amount_invested"] == 100000.0
    # Months 2-12 have 0 investment
    for i in range(1, 12):
        assert installments[i]["amount_invested"] == 0.0


# ---------------------------------------------------------------------------
# Tests — payout helper
# ---------------------------------------------------------------------------

def test_payout_to_period():
    from app.fd_database import _payout_to_period
    assert _payout_to_period("Monthly") == 1
    assert _payout_to_period("Quarterly") == 3
    assert _payout_to_period("Quartely") == 3  # typo variant
    assert _payout_to_period("Half-Yearly") == 6
    assert _payout_to_period("Semi-Annual") == 6
    assert _payout_to_period("Annually") == 12
    assert _payout_to_period("Yearly") == 12
    assert _payout_to_period("unknown") == 3  # default


# ---------------------------------------------------------------------------
# Tests — delete
# ---------------------------------------------------------------------------

def test_delete_xlsx_fd(fd_base_dir):
    from app.fd_database import add, delete, get_all
    data = {
        "bank": "HDFC",
        "principal": 50000,
        "interest_rate": 6.5,
        "tenure_months": 24,
        "start_date": "2024-01-01",
    }
    result = add(data, base_dir=str(fd_base_dir))
    fd_id = result["id"]

    # Confirm it's there
    items = get_all(base_dir=str(fd_base_dir))
    assert len(items) == 1

    # Delete
    del_result = delete(fd_id, base_dir=str(fd_base_dir))
    assert "deleted" in del_result["message"]

    # Verify gone
    items = get_all(base_dir=str(fd_base_dir))
    assert len(items) == 0


def test_delete_nonexistent_raises(fd_base_dir):
    from app.fd_database import delete
    with pytest.raises(ValueError, match="not found"):
        delete("nonexistent", base_dir=str(fd_base_dir))


# ---------------------------------------------------------------------------
# Tests — JSON manual entries (update path)
# ---------------------------------------------------------------------------

def test_update_json_entry(fd_base_dir):
    from app.fd_database import _save_json, _load_json, update
    json_file = fd_base_dir / "fixed_deposits.json"

    # Seed a manual JSON entry
    entry = {
        "id": "test1234",
        "bank": "ICICI",
        "principal": 200000,
        "interest_rate": 7.5,
        "tenure_months": 36,
        "start_date": "2023-06-01",
        "maturity_date": "2026-06-01",
        "interest_payout": "Quarterly",
        "status": "Active",
        "remarks": "",
        "tds": 0,
        "type": "FD",
        "name": "ICICI FD",
    }
    _save_json([entry], json_file=json_file, dumps_dir=fd_base_dir)

    # Update
    result = update("test1234", {"principal": 250000}, base_dir=str(fd_base_dir))
    assert result["principal"] == 250000
    # maturity recalculated
    assert result["maturity_amount"] > 250000


def test_update_nonexistent_raises(fd_base_dir):
    from app.fd_database import update
    # Create empty JSON
    json_file = fd_base_dir / "fixed_deposits.json"
    json_file.write_text("[]")
    with pytest.raises(ValueError, match="not found"):
        update("nope", {"bank": "X"}, base_dir=str(fd_base_dir))


# ---------------------------------------------------------------------------
# Tests — dashboard aggregation
# ---------------------------------------------------------------------------

def test_dashboard_after_add(fd_base_dir):
    from app.fd_database import add, get_dashboard
    add({
        "bank": "Axis",
        "principal": 100000,
        "interest_rate": 7.0,
        "tenure_months": 36,
        "start_date": "2025-01-01",
    }, base_dir=str(fd_base_dir))
    add({
        "bank": "SBI",
        "principal": 200000,
        "interest_rate": 6.5,
        "tenure_months": 36,
        "start_date": "2025-06-01",
    }, base_dir=str(fd_base_dir))

    dash = get_dashboard(base_dir=str(fd_base_dir))
    assert dash["total_count"] == 2
    # Both should be active (maturity 3 years out)
    assert dash["active_count"] == 2
    assert dash["total_invested"] == 300000.0


# ---------------------------------------------------------------------------
# Tests — gen_fd_id determinism
# ---------------------------------------------------------------------------

def test_gen_fd_id_deterministic():
    from app.fd_database import _gen_fd_id
    assert _gen_fd_id("SBI FD") == _gen_fd_id("SBI FD")
    assert _gen_fd_id("SBI FD") != _gen_fd_id("HDFC FD")


# ---------------------------------------------------------------------------
# Tests — enrich JSON item
# ---------------------------------------------------------------------------

def test_enrich_json_item_sets_computed_fields():
    from app.fd_database import _enrich_json_item
    item = {
        "id": "abc",
        "bank": "Test",
        "principal": 100000,
        "interest_rate": 8.0,
        "tenure_months": 12,
        "start_date": "2020-01-01",
        "maturity_date": "2021-01-01",
        "type": "FD",
    }
    enriched = _enrich_json_item(item)
    assert enriched["source"] == "manual"
    assert enriched["total_invested"] == 100000
    assert enriched["maturity_amount"] > 100000
    assert "installments" in enriched
    assert enriched["installments_total"] == 12
    assert enriched["status"] == "Matured"  # maturity date in the past
