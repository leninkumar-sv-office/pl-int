"""Unit tests for app/sip_manager.py — SIP configuration manager."""
import json
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from app.sip_manager import SIPManager


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sip_mgr(tmp_path):
    """Create a SIPManager with a temp config file."""
    config_file = tmp_path / "sip_config.json"
    return SIPManager(config_file=config_file)


# ---------------------------------------------------------------------------
# Tests — empty state
# ---------------------------------------------------------------------------

def test_load_configs_empty(sip_mgr):
    configs = sip_mgr.load_configs()
    assert configs == []


def test_config_file_created(sip_mgr):
    assert sip_mgr.config_file.exists()
    data = json.loads(sip_mgr.config_file.read_text())
    assert "sip_configs" in data


# ---------------------------------------------------------------------------
# Tests — add_sip
# ---------------------------------------------------------------------------

def test_add_sip(sip_mgr):
    result = sip_mgr.add_sip(
        fund_code="INF200K01RJ1",
        fund_name="SBI Small Cap Fund",
        amount=5000,
        frequency="monthly",
        sip_date=5,
        start_date="2024-01-01",
    )
    assert result["fund_code"] == "INF200K01RJ1"
    assert result["fund_name"] == "SBI Small Cap Fund"
    assert result["amount"] == 5000
    assert result["frequency"] == "monthly"
    assert result["sip_date"] == 5
    assert result["enabled"] is True
    assert result["next_sip_date"]  # should be computed

    configs = sip_mgr.load_configs()
    assert len(configs) == 1


def test_add_sip_upserts_existing(sip_mgr):
    sip_mgr.add_sip(
        fund_code="INF100",
        fund_name="Fund A",
        amount=1000,
    )
    sip_mgr.add_sip(
        fund_code="INF100",
        fund_name="Fund A Updated",
        amount=2000,
    )
    configs = sip_mgr.load_configs()
    assert len(configs) == 1
    assert configs[0]["amount"] == 2000
    assert configs[0]["fund_name"] == "Fund A Updated"


def test_add_multiple_sips(sip_mgr):
    for i in range(3):
        sip_mgr.add_sip(
            fund_code=f"INF{i:03d}",
            fund_name=f"Fund {i}",
            amount=1000 * (i + 1),
        )
    configs = sip_mgr.load_configs()
    assert len(configs) == 3


# ---------------------------------------------------------------------------
# Tests — update_sip
# ---------------------------------------------------------------------------

def test_update_sip(sip_mgr):
    sip_mgr.add_sip(fund_code="INF200", fund_name="Fund B", amount=3000)
    updated = sip_mgr.update_sip("INF200", amount=5000, notes="Increased")
    assert updated["amount"] == 5000
    assert updated["notes"] == "Increased"


def test_update_sip_recomputes_next_date_on_frequency_change(sip_mgr):
    sip_mgr.add_sip(
        fund_code="INF300",
        fund_name="Fund C",
        amount=2000,
        frequency="monthly",
        sip_date=10,
        start_date="2024-01-01",
    )
    original = sip_mgr.load_configs()[0]
    original_next = original["next_sip_date"]

    updated = sip_mgr.update_sip("INF300", frequency="quarterly")
    assert updated["next_sip_date"] != original_next


def test_update_nonexistent_raises(sip_mgr):
    with pytest.raises(ValueError, match="not found"):
        sip_mgr.update_sip("NONEXIST", amount=0)


# ---------------------------------------------------------------------------
# Tests — delete_sip
# ---------------------------------------------------------------------------

def test_delete_sip(sip_mgr):
    sip_mgr.add_sip(fund_code="INF400", fund_name="Fund D", amount=1000)
    assert len(sip_mgr.load_configs()) == 1

    sip_mgr.delete_sip("INF400")
    assert len(sip_mgr.load_configs()) == 0


def test_delete_nonexistent_no_error(sip_mgr):
    """Deleting a non-existent SIP just leaves configs unchanged."""
    sip_mgr.add_sip(fund_code="INF500", fund_name="Fund E", amount=1000)
    sip_mgr.delete_sip("NOPE")
    assert len(sip_mgr.load_configs()) == 1


# ---------------------------------------------------------------------------
# Tests — get_pending_sips
# ---------------------------------------------------------------------------

def test_get_pending_sips(sip_mgr):
    # Add a SIP with a past next_sip_date
    sip_mgr.add_sip(
        fund_code="INF600",
        fund_name="Fund F",
        amount=2000,
        start_date="2020-01-01",
        sip_date=1,
    )
    # Manually set next_sip_date to today so it's pending
    configs = sip_mgr.load_configs()
    configs[0]["next_sip_date"] = datetime.now().strftime("%Y-%m-%d")
    sip_mgr._save_configs(configs)

    pending = sip_mgr.get_pending_sips()
    assert len(pending) == 1
    assert pending[0]["fund_code"] == "INF600"


def test_get_pending_sips_excludes_disabled(sip_mgr):
    sip_mgr.add_sip(
        fund_code="INF700",
        fund_name="Fund G",
        amount=1000,
        enabled=False,
    )
    # Even if next_sip_date is today, disabled SIPs should be excluded
    configs = sip_mgr.load_configs()
    configs[0]["next_sip_date"] = datetime.now().strftime("%Y-%m-%d")
    sip_mgr._save_configs(configs)

    pending = sip_mgr.get_pending_sips()
    assert len(pending) == 0


def test_get_pending_sips_excludes_ended(sip_mgr):
    sip_mgr.add_sip(
        fund_code="INF800",
        fund_name="Fund H",
        amount=1000,
        end_date="2020-01-01",  # ended in the past
    )
    configs = sip_mgr.load_configs()
    configs[0]["next_sip_date"] = datetime.now().strftime("%Y-%m-%d")
    sip_mgr._save_configs(configs)

    pending = sip_mgr.get_pending_sips()
    assert len(pending) == 0


# ---------------------------------------------------------------------------
# Tests — mark_processed
# ---------------------------------------------------------------------------

def test_mark_processed(sip_mgr):
    sip_mgr.add_sip(
        fund_code="INF900",
        fund_name="Fund I",
        amount=3000,
        sip_date=15,
    )
    today_str = datetime.now().strftime("%Y-%m-%d")
    result = sip_mgr.mark_processed("INF900", today_str)
    assert result["last_processed"] == today_str
    # next_sip_date should be advanced
    assert result["next_sip_date"] > today_str


def test_mark_processed_nonexistent_raises(sip_mgr):
    with pytest.raises(ValueError, match="not found"):
        sip_mgr.mark_processed("NOPE")


# ---------------------------------------------------------------------------
# Tests — _compute_next_sip_date
# ---------------------------------------------------------------------------

def test_compute_next_sip_date_monthly():
    today = datetime.now()
    # Pick a sip_date in the future this month
    future_day = min(28, today.day + 5)
    result = SIPManager._compute_next_sip_date(
        "monthly", future_day, today.strftime("%Y-%m-%d")
    )
    parsed = datetime.strptime(result, "%Y-%m-%d")
    assert parsed >= today


def test_compute_next_sip_date_weekly():
    today = datetime.now()
    result = SIPManager._compute_next_sip_date(
        "weekly", 1, today.strftime("%Y-%m-%d")  # Monday
    )
    parsed = datetime.strptime(result, "%Y-%m-%d")
    assert parsed > today
    assert parsed.weekday() == 0  # Monday


def test_compute_next_sip_date_quarterly():
    today = datetime.now()
    result = SIPManager._compute_next_sip_date(
        "quarterly", 10, today.strftime("%Y-%m-%d")
    )
    parsed = datetime.strptime(result, "%Y-%m-%d")
    assert parsed > today


# ---------------------------------------------------------------------------
# Tests — load_configs with corrupt/missing file (covers lines 36-37)
# ---------------------------------------------------------------------------

def test_load_configs_corrupt_json(tmp_path):
    """load_configs returns [] when file contains invalid JSON."""
    config_file = tmp_path / "sip_config.json"
    config_file.write_text("NOT VALID JSON!!!")
    mgr = SIPManager(config_file=config_file)
    assert mgr.load_configs() == []


def test_load_configs_file_deleted_after_init(tmp_path):
    """load_configs returns [] when file is deleted after initialization."""
    config_file = tmp_path / "sip_config.json"
    mgr = SIPManager(config_file=config_file)
    # File exists after init, delete it
    config_file.unlink()
    assert mgr.load_configs() == []


# ---------------------------------------------------------------------------
# Tests — _compute_next_sip_date edge cases
# ---------------------------------------------------------------------------

def test_compute_next_sip_date_quarterly_wraps_year():
    """Quarterly from a future October: month+3=13 wraps to Jan next year."""
    # Use a future date in October so ref.month = 10, next_month = 13 > 12
    future_oct = datetime(datetime.now().year + 1, 10, 15)
    result = SIPManager._compute_next_sip_date(
        "quarterly", 10, future_oct.strftime("%Y-%m-%d")
    )
    parsed = datetime.strptime(result, "%Y-%m-%d")
    assert parsed > future_oct
    assert parsed.month == 1  # wrapped to January


def test_compute_next_sip_date_quarterly_future_date():
    """Quarterly from a future date beyond next quarter."""
    result = SIPManager._compute_next_sip_date(
        "quarterly", 10, (datetime.now() + timedelta(days=365)).strftime("%Y-%m-%d")
    )
    parsed = datetime.strptime(result, "%Y-%m-%d")
    assert parsed > datetime.now()


def test_compute_next_sip_date_monthly_wraps_december():
    """Monthly from a future December wraps to January next year (lines 207-208)."""
    # Use a future date in December so ref.month = 12
    future_dec = datetime(datetime.now().year + 1, 12, 20)
    result = SIPManager._compute_next_sip_date(
        "monthly", 15, future_dec.strftime("%Y-%m-%d")
    )
    parsed = datetime.strptime(result, "%Y-%m-%d")
    assert parsed > future_dec
    assert parsed.month == 1  # wrapped to January
    assert parsed.year == future_dec.year + 1


def test_compute_next_sip_date_invalid_from_date():
    """Invalid from_date falls back to datetime.now()."""
    result = SIPManager._compute_next_sip_date(
        "monthly", 15, "not-a-date"
    )
    parsed = datetime.strptime(result, "%Y-%m-%d")
    assert parsed >= datetime.now()
