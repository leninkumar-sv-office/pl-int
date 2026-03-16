"""Unit tests for app/ppf_database.py — PPF database layer."""
import json
from pathlib import Path
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def ppf_base_dir(tmp_path):
    """Create a temp base dir with PPF subdir."""
    (tmp_path / "PPF").mkdir()
    return tmp_path


@pytest.fixture(autouse=True)
def _mock_drive():
    with patch("app.ppf_database._sync_to_drive"), \
         patch("app.ppf_database._delete_from_drive"):
        yield


# ---------------------------------------------------------------------------
# Tests — empty state
# ---------------------------------------------------------------------------

def test_get_all_empty(ppf_base_dir):
    from app.ppf_database import get_all
    assert get_all(base_dir=str(ppf_base_dir)) == []


def test_get_dashboard_empty(ppf_base_dir):
    from app.ppf_database import get_dashboard
    dash = get_dashboard(base_dir=str(ppf_base_dir))
    assert dash["active_count"] == 0
    assert dash["total_count"] == 0
    assert dash["total_deposited"] == 0


# ---------------------------------------------------------------------------
# Tests — add SIP-based account
# ---------------------------------------------------------------------------

def test_add_sip_ppf(ppf_base_dir):
    from app.ppf_database import add, get_all
    data = {
        "account_name": "My PPF",
        "bank": "SBI",
        "interest_rate": 7.1,
        "start_date": "2020-01-01",
        "tenure_years": 15,
        "payment_type": "sip",
        "sip_amount": 5000,
        "sip_frequency": "monthly",
        "account_number": "PPF12345",
    }
    result = add(data, base_dir=str(ppf_base_dir))
    assert result["bank"] == "SBI"
    assert result["interest_rate"] == 7.1
    assert result["tenure_years"] == 15
    assert result["sip_amount"] == 5000
    assert result["source"] == "xlsx"

    # xlsx created
    xlsx_files = list((ppf_base_dir / "PPF").glob("*.xlsx"))
    assert len(xlsx_files) == 1

    # get_all picks it up
    items = get_all(base_dir=str(ppf_base_dir))
    assert len(items) == 1


def test_add_one_time_ppf(ppf_base_dir):
    from app.ppf_database import add
    data = {
        "account_name": "One Time PPF",
        "bank": "Post Office",
        "interest_rate": 7.1,
        "start_date": "2020-04-01",
        "tenure_years": 15,
        "payment_type": "one_time",
        "amount_added": 150000,
    }
    result = add(data, base_dir=str(ppf_base_dir))
    assert result["total_deposited"] > 0


# ---------------------------------------------------------------------------
# Tests — delete
# ---------------------------------------------------------------------------

def test_delete_ppf(ppf_base_dir):
    from app.ppf_database import add, delete, get_all
    data = {
        "account_name": "Del PPF",
        "bank": "SBI",
        "start_date": "2020-01-01",
        "tenure_years": 15,
        "sip_amount": 1000,
        "sip_frequency": "monthly",
    }
    result = add(data, base_dir=str(ppf_base_dir))
    ppf_id = result["id"]

    items = get_all(base_dir=str(ppf_base_dir))
    assert len(items) == 1

    del_result = delete(ppf_id, base_dir=str(ppf_base_dir))
    assert "deleted" in del_result["message"]

    items = get_all(base_dir=str(ppf_base_dir))
    assert len(items) == 0


def test_delete_nonexistent_raises(ppf_base_dir):
    from app.ppf_database import delete
    with pytest.raises(ValueError, match="not found"):
        delete("badid", base_dir=str(ppf_base_dir))


# ---------------------------------------------------------------------------
# Tests — update
# ---------------------------------------------------------------------------

def test_update_ppf(ppf_base_dir):
    from app.ppf_database import add, update
    data = {
        "account_name": "Upd PPF",
        "bank": "SBI",
        "start_date": "2020-01-01",
        "tenure_years": 15,
        "sip_amount": 5000,
        "sip_frequency": "monthly",
    }
    result = add(data, base_dir=str(ppf_base_dir))
    ppf_id = result["id"]

    updated = update(ppf_id, {"bank": "PNB"}, base_dir=str(ppf_base_dir))
    assert updated["bank"] == "PNB"


# ---------------------------------------------------------------------------
# Tests — add_contribution
# ---------------------------------------------------------------------------

def test_add_contribution(ppf_base_dir):
    from app.ppf_database import add, add_contribution, get_all
    data = {
        "account_name": "Contrib PPF",
        "bank": "SBI",
        "start_date": "2020-01-01",
        "tenure_years": 15,
        "sip_amount": 5000,
        "sip_frequency": "monthly",
    }
    result = add(data, base_dir=str(ppf_base_dir))
    ppf_id = result["id"]

    contrib_result = add_contribution(ppf_id, {
        "date": "2024-06-15",
        "amount": 50000,
        "remarks": "Lump sum",
    }, base_dir=str(ppf_base_dir))
    assert contrib_result is not None

    # Verify contribution is reflected
    items = get_all(base_dir=str(ppf_base_dir))
    assert len(items) == 1
    contribs = items[0].get("contributions", [])
    assert len(contribs) >= 1


# ---------------------------------------------------------------------------
# Tests — helpers
# ---------------------------------------------------------------------------

def test_gen_ppf_id_deterministic():
    from app.ppf_database import _gen_ppf_id
    assert _gen_ppf_id("My PPF") == _gen_ppf_id("My PPF")
    assert _gen_ppf_id("PPF A") != _gen_ppf_id("PPF B")


def test_sip_freq_to_months():
    from app.ppf_database import _sip_freq_to_months
    assert _sip_freq_to_months("monthly") == 1
    assert _sip_freq_to_months("Monthly") == 1
    assert _sip_freq_to_months("quarterly") == 3
    assert _sip_freq_to_months("yearly") == 12
    assert _sip_freq_to_months("annual") == 12
    assert _sip_freq_to_months("unknown") == 1  # default


def test_get_financial_year():
    from app.ppf_database import _get_financial_year
    from datetime import date
    assert _get_financial_year(date(2024, 4, 1)) == "2024-25"
    assert _get_financial_year(date(2024, 3, 31)) == "2023-24"
    assert _get_financial_year(date(2024, 1, 1)) == "2023-24"


# ---------------------------------------------------------------------------
# Tests — dashboard
# ---------------------------------------------------------------------------

def test_dashboard_after_add(ppf_base_dir):
    from app.ppf_database import add, get_dashboard
    add({
        "account_name": "Dash PPF",
        "bank": "SBI",
        "start_date": "2020-01-01",
        "tenure_years": 15,
        "sip_amount": 5000,
        "sip_frequency": "monthly",
    }, base_dir=str(ppf_base_dir))

    dash = get_dashboard(base_dir=str(ppf_base_dir))
    assert dash["total_count"] == 1
    assert dash["active_count"] == 1
    assert dash["total_deposited"] > 0


# ---------------------------------------------------------------------------
# Tests — installments structure
# ---------------------------------------------------------------------------

def test_installments_have_correct_fields(ppf_base_dir):
    from app.ppf_database import add
    result = add({
        "account_name": "Inst PPF",
        "bank": "SBI",
        "start_date": "2020-01-01",
        "tenure_years": 15,
        "sip_amount": 5000,
        "sip_frequency": "monthly",
    }, base_dir=str(ppf_base_dir))

    assert result["installments_total"] == 180  # 15 years * 12 months
    first = result["installments"][0]
    assert "month" in first
    assert "date" in first
    assert "amount_invested" in first
    assert "is_past" in first
    assert "lock_status" in first
