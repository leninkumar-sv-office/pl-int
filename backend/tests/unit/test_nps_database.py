"""Unit tests for app/nps_database.py — NPS database layer."""
import json
from pathlib import Path
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def nps_base_dir(tmp_path):
    """Create a temp base dir with NPS subdir."""
    (tmp_path / "NPS").mkdir()
    return tmp_path


@pytest.fixture(autouse=True)
def _mock_drive_and_import():
    """Mock drive + skip PDF import (no PDF_IMPORT_DIR in tests)."""
    with patch("app.nps_database._sync_to_drive"), \
         patch("app.nps_database._delete_from_drive"), \
         patch("app.nps_database._imported", True):
        yield


def _get_nps_id(nps_base_dir):
    """Helper: get the actual persisted ID from get_all (may differ from add's return)."""
    from app.nps_database import get_all
    items = get_all(base_dir=str(nps_base_dir))
    assert len(items) >= 1
    return items[-1]["id"]


# ---------------------------------------------------------------------------
# Tests — empty state
# ---------------------------------------------------------------------------

def test_get_all_empty(nps_base_dir):
    from app.nps_database import get_all
    assert get_all(base_dir=str(nps_base_dir)) == []


def test_get_dashboard_empty(nps_base_dir):
    from app.nps_database import get_dashboard
    dash = get_dashboard(base_dir=str(nps_base_dir))
    assert dash["active_count"] == 0
    assert dash["total_count"] == 0
    assert dash["total_contributed"] == 0
    assert dash["current_value"] == 0


# ---------------------------------------------------------------------------
# Tests — add
# ---------------------------------------------------------------------------

def test_add_nps_account(nps_base_dir):
    from app.nps_database import add, get_all
    data = {
        "account_name": "My NPS",
        "pran": "110012345678",
        "tier": "Tier I",
        "fund_manager": "SBI Pension Fund",
        "scheme_preference": "Auto Choice",
        "start_date": "2019-01-01",
        "current_value": 500000,
        "status": "Active",
    }
    result = add(data, base_dir=str(nps_base_dir))
    assert result["pran"] == "110012345678"
    assert result["account_name"] == "My NPS"
    assert result["current_value"] == 500000

    # xlsx created
    xlsx_files = list((nps_base_dir / "NPS").glob("*.xlsx"))
    assert len(xlsx_files) == 1

    items = get_all(base_dir=str(nps_base_dir))
    assert len(items) == 1
    assert items[0]["pran"] == "110012345678"


# ---------------------------------------------------------------------------
# Tests — update
# ---------------------------------------------------------------------------

def test_update_nps(nps_base_dir):
    from app.nps_database import add, update, get_all
    add({
        "account_name": "Upd NPS",
        "pran": "110099887766",
        "start_date": "2020-01-01",
        "current_value": 100000,
    }, base_dir=str(nps_base_dir))
    # Re-read to get the actual persisted ID
    nps_id = _get_nps_id(nps_base_dir)

    updated = update(nps_id, {"current_value": 200000}, base_dir=str(nps_base_dir))
    assert updated["current_value"] == 200000


def test_update_nonexistent_raises(nps_base_dir):
    from app.nps_database import update
    with pytest.raises(ValueError, match="not found"):
        update("bad_id", {"current_value": 0}, base_dir=str(nps_base_dir))


# ---------------------------------------------------------------------------
# Tests — delete
# ---------------------------------------------------------------------------

def test_delete_nps(nps_base_dir):
    from app.nps_database import add, delete, get_all
    add({
        "account_name": "Del NPS",
        "pran": "110000000001",
        "start_date": "2020-01-01",
    }, base_dir=str(nps_base_dir))
    nps_id = _get_nps_id(nps_base_dir)

    items = get_all(base_dir=str(nps_base_dir))
    assert len(items) == 1

    del_result = delete(nps_id, base_dir=str(nps_base_dir))
    assert "deleted" in del_result["message"]

    items = get_all(base_dir=str(nps_base_dir))
    assert len(items) == 0


def test_delete_nonexistent_raises(nps_base_dir):
    from app.nps_database import delete
    with pytest.raises(ValueError, match="not found"):
        delete("bad_id", base_dir=str(nps_base_dir))


# ---------------------------------------------------------------------------
# Tests — add_contribution
# ---------------------------------------------------------------------------

def test_add_contribution(nps_base_dir):
    from app.nps_database import add, add_contribution, get_all
    add({
        "account_name": "Contrib NPS",
        "pran": "110000000002",
        "start_date": "2020-01-01",
        "current_value": 100000,
    }, base_dir=str(nps_base_dir))
    nps_id = _get_nps_id(nps_base_dir)

    updated = add_contribution(nps_id, {
        "date": "2024-06-15",
        "amount": 50000,
        "remarks": "FY 2024-25",
    }, base_dir=str(nps_base_dir))
    assert len(updated["contributions"]) == 1
    assert updated["contributions"][0]["amount"] == 50000

    # Verify on reload
    items = get_all(base_dir=str(nps_base_dir))
    assert len(items[0]["contributions"]) == 1


def test_add_contribution_invalid_date(nps_base_dir):
    from app.nps_database import add, add_contribution
    add({
        "account_name": "Date NPS",
        "pran": "110000000003",
        "start_date": "2020-01-01",
    }, base_dir=str(nps_base_dir))
    nps_id = _get_nps_id(nps_base_dir)

    with pytest.raises(ValueError, match="Invalid date format"):
        add_contribution(nps_id, {
            "date": "not-a-date",
            "amount": 1000,
        }, base_dir=str(nps_base_dir))


# ---------------------------------------------------------------------------
# Tests — enrich computes gains
# ---------------------------------------------------------------------------

def test_enrich_calculates_gains(nps_base_dir):
    from app.nps_database import add, add_contribution, get_all
    add({
        "account_name": "Gain NPS",
        "pran": "110000000004",
        "start_date": "2020-01-01",
        "current_value": 200000,
    }, base_dir=str(nps_base_dir))
    nps_id = _get_nps_id(nps_base_dir)

    add_contribution(nps_id, {
        "date": "2020-06-01",
        "amount": 100000,
    }, base_dir=str(nps_base_dir))

    items = get_all(base_dir=str(nps_base_dir))
    item = items[0]
    assert item["total_contributed"] == 100000
    assert item["gain"] == 100000  # 200000 - 100000
    assert item["gain_pct"] == 100.0


# ---------------------------------------------------------------------------
# Tests — dashboard
# ---------------------------------------------------------------------------

def test_dashboard_after_add(nps_base_dir):
    from app.nps_database import add, get_dashboard
    add({
        "account_name": "Dash NPS",
        "pran": "110000000005",
        "start_date": "2020-01-01",
        "current_value": 300000,
    }, base_dir=str(nps_base_dir))

    dash = get_dashboard(base_dir=str(nps_base_dir))
    assert dash["total_count"] == 1
    assert dash["active_count"] == 1
    assert dash["current_value"] == 300000


# ---------------------------------------------------------------------------
# Tests — helpers
# ---------------------------------------------------------------------------

def test_gen_id_deterministic():
    from app.nps_database import _gen_id
    assert _gen_id("pran123") == _gen_id("pran123")
    assert _gen_id("a") != _gen_id("b")


def test_parse_num():
    from app.nps_database import _parse_num
    assert _parse_num("1,234.56") == 1234.56
    assert _parse_num("(500.00)") == -500.0
    assert _parse_num("abc") == 0.0


def test_to_float():
    from app.nps_database import _to_float
    assert _to_float(3.14) == 3.14
    assert _to_float(None) == 0.0
    assert _to_float("bad") == 0.0
