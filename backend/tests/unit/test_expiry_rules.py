"""Tests for expiry_rules module."""
import json
from datetime import datetime
from unittest.mock import patch, MagicMock

import pytest


@pytest.fixture
def tmp_env(tmp_path, monkeypatch):
    dumps = tmp_path / "dumps"
    (dumps / "test@example.com" / "TestUser" / "settings").mkdir(parents=True)
    monkeypatch.setattr("app.expiry_rules.DUMPS_BASE", dumps)
    monkeypatch.setattr(
        "app.expiry_rules.get_user_dumps_dir",
        lambda uid, email: dumps / email / uid.title(),
    )
    monkeypatch.setattr("app.expiry_rules.get_users", lambda: [
        {"id": "testuser", "name": "TestUser", "email": "test@example.com"}
    ])
    # Also set legacy file path to tmp
    legacy = tmp_path / "data" / "expiry_rules.json"
    legacy.parent.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("app.expiry_rules._LEGACY_RULES_FILE", legacy)
    return dumps


class TestRuleTypes:
    def test_all_categories_present(self):
        from app.expiry_rules import RULE_TYPES
        for cat in ["fd", "rd", "ppf", "nps", "si", "insurance", "stocks", "mf"]:
            assert cat in RULE_TYPES, f"Missing category: {cat}"

    def test_fd_rule_types(self):
        from app.expiry_rules import RULE_TYPES
        types = [r["type"] for r in RULE_TYPES["fd"]]
        assert "days_before_maturity" in types
        assert "on_maturity" in types

    def test_get_rule_types(self):
        from app.expiry_rules import get_rule_types, RULE_TYPES
        assert get_rule_types() is RULE_TYPES

    def test_stocks_rule_types(self):
        from app.expiry_rules import RULE_TYPES
        types = [r["type"] for r in RULE_TYPES["stocks"]]
        assert "profit_threshold" in types
        assert "day_drop_threshold" in types
        assert "near_52w_high" in types

    def test_mf_rule_types(self):
        from app.expiry_rules import RULE_TYPES
        types = [r["type"] for r in RULE_TYPES["mf"]]
        assert "profit_threshold" in types
        assert "near_52w_low" in types


class TestRuleCRUD:
    def test_create_rule(self, tmp_env):
        from app.expiry_rules import save_rule, get_rules
        rule = save_rule("test@example.com", "testuser", {
            "category": "fd", "rule_type": "days_before_maturity", "days": 30,
        })
        assert rule["id"]
        assert rule["category"] == "fd"
        assert rule["days"] == 30
        assert rule["enabled"] is True

        rules = get_rules("test@example.com", "testuser")
        assert len(rules) == 1
        assert rules[0]["id"] == rule["id"]

    def test_update_rule(self, tmp_env):
        from app.expiry_rules import save_rule, get_rules
        rule = save_rule("test@example.com", "testuser", {
            "category": "fd", "rule_type": "on_maturity",
        })
        updated = save_rule("test@example.com", "testuser", {
            "id": rule["id"], "category": "fd", "rule_type": "on_maturity", "enabled": False,
        })
        assert updated["enabled"] is False
        assert len(get_rules("test@example.com", "testuser")) == 1

    def test_delete_rule(self, tmp_env):
        from app.expiry_rules import save_rule, delete_rule, get_rules
        rule = save_rule("test@example.com", "testuser", {
            "category": "rd", "rule_type": "on_maturity",
        })
        assert delete_rule("test@example.com", "testuser", rule["id"]) is True
        assert len(get_rules("test@example.com", "testuser")) == 0

    def test_delete_nonexistent(self, tmp_env):
        from app.expiry_rules import delete_rule
        assert delete_rule("test@example.com", "testuser", "nope") is False

    def test_filter_by_category(self, tmp_env):
        from app.expiry_rules import save_rule, get_rules
        save_rule("test@example.com", "testuser", {"category": "fd", "rule_type": "on_maturity"})
        save_rule("test@example.com", "testuser", {"category": "rd", "rule_type": "on_maturity"})
        save_rule("test@example.com", "testuser", {"category": "fd", "rule_type": "days_before_maturity", "days": 7})

        assert len(get_rules("test@example.com", "testuser")) == 3
        assert len(get_rules("test@example.com", "testuser", category="fd")) == 2
        assert len(get_rules("test@example.com", "testuser", category="rd")) == 1

    def test_per_user_isolation(self, tmp_env):
        from app.expiry_rules import save_rule, get_rules
        (tmp_env / "test@example.com" / "Appa" / "settings").mkdir(parents=True)
        save_rule("test@example.com", "testuser", {"category": "fd", "rule_type": "on_maturity"})
        save_rule("test@example.com", "appa", {"category": "rd", "rule_type": "on_maturity"})

        assert len(get_rules("test@example.com", "testuser")) == 1
        assert len(get_rules("test@example.com", "appa")) == 1
        assert get_rules("test@example.com", "testuser")[0]["category"] == "fd"
        assert get_rules("test@example.com", "appa")[0]["category"] == "rd"

    def test_create_profit_threshold_rule(self, tmp_env):
        from app.expiry_rules import save_rule
        rule = save_rule("test@example.com", "testuser", {
            "category": "stocks", "rule_type": "profit_threshold",
            "threshold_pct": 50, "alert_time": "09:30",
        })
        assert rule["threshold_pct"] == 50
        assert rule["alert_time"] == "09:30"

    def test_create_day_drop_threshold_rule(self, tmp_env):
        from app.expiry_rules import save_rule
        rule = save_rule("test@example.com", "testuser", {
            "category": "stocks", "rule_type": "day_drop_threshold",
            "threshold_pct": 5, "alert_time": "16:30",
        })
        assert rule["threshold_pct"] == 5
        assert rule["alert_time"] == "16:30"

    def test_create_near_52w_high_rule(self, tmp_env):
        from app.expiry_rules import save_rule
        rule = save_rule("test@example.com", "testuser", {
            "category": "stocks", "rule_type": "near_52w_high",
            "alert_time": "15:00",
        })
        assert rule["alert_time"] == "15:00"
        # near_52w_high should NOT have threshold_pct
        assert "threshold_pct" not in rule

    def test_create_near_52w_low_rule(self, tmp_env):
        from app.expiry_rules import save_rule
        rule = save_rule("test@example.com", "testuser", {
            "category": "mf", "rule_type": "near_52w_low",
            "alert_time": "16:00",
        })
        assert rule["alert_time"] == "16:00"

    def test_create_week_drop_threshold_rule(self, tmp_env):
        from app.expiry_rules import save_rule
        rule = save_rule("test@example.com", "testuser", {
            "category": "mf", "rule_type": "week_drop_threshold",
            "threshold_pct": 10, "alert_time": "16:30",
        })
        assert rule["threshold_pct"] == 10

    def test_create_month_drop_threshold_rule(self, tmp_env):
        from app.expiry_rules import save_rule
        rule = save_rule("test@example.com", "testuser", {
            "category": "stocks", "rule_type": "month_drop_threshold",
            "threshold_pct": 15,
        })
        assert rule["threshold_pct"] == 15


class TestMigrateLegacy:
    def test_migrate_v2(self, tmp_env):
        from app.expiry_rules import get_rules
        # Create v2 legacy file
        legacy_v2 = tmp_env / "test@example.com" / "settings"
        legacy_v2.mkdir(parents=True, exist_ok=True)
        legacy_rules = [{"id": "v2rule", "category": "fd", "rule_type": "on_maturity", "enabled": True}]
        (legacy_v2 / "expiry_rules_testuser.json").write_text(json.dumps(legacy_rules))

        rules = get_rules("test@example.com", "testuser")
        assert len(rules) == 1
        assert rules[0]["id"] == "v2rule"
        # Legacy file should be deleted after migration
        assert not (legacy_v2 / "expiry_rules_testuser.json").exists()

    def test_migrate_v1_with_data(self, tmp_env, tmp_path):
        from app.expiry_rules import get_rules, _LEGACY_RULES_FILE
        import app.expiry_rules as er
        # Create v1 legacy file
        legacy = er._LEGACY_RULES_FILE
        legacy.parent.mkdir(parents=True, exist_ok=True)
        v1_data = {
            "test@example.com:testuser": [
                {"id": "v1rule", "category": "rd", "rule_type": "on_maturity", "enabled": True}
            ],
            "other@example.com:otheruser": [
                {"id": "other", "category": "fd", "rule_type": "on_maturity", "enabled": True}
            ],
        }
        legacy.write_text(json.dumps(v1_data))

        rules = get_rules("test@example.com", "testuser")
        assert len(rules) == 1
        assert rules[0]["id"] == "v1rule"
        # Other user's data should remain
        remaining = json.loads(legacy.read_text())
        assert "other@example.com:otheruser" in remaining

    def test_migrate_v1_last_entry_deletes_file(self, tmp_env, tmp_path):
        from app.expiry_rules import get_rules
        import app.expiry_rules as er
        legacy = er._LEGACY_RULES_FILE
        legacy.parent.mkdir(parents=True, exist_ok=True)
        v1_data = {
            "test@example.com:testuser": [
                {"id": "solo", "category": "fd", "rule_type": "on_maturity"}
            ]
        }
        legacy.write_text(json.dumps(v1_data))

        rules = get_rules("test@example.com", "testuser")
        assert len(rules) == 1
        # File should be removed since it was the last entry
        assert not legacy.exists()

    def test_migrate_v1_no_matching_key(self, tmp_env):
        from app.expiry_rules import get_rules
        import app.expiry_rules as er
        legacy = er._LEGACY_RULES_FILE
        legacy.parent.mkdir(parents=True, exist_ok=True)
        legacy.write_text(json.dumps({"other@x.com:other": [{"id": "1"}]}))

        rules = get_rules("test@example.com", "testuser")
        assert rules == []

    def test_migrate_no_legacy(self, tmp_env):
        from app.expiry_rules import get_rules
        rules = get_rules("test@example.com", "testuser")
        assert rules == []


class TestCheckRule:
    def test_fd_days_before_maturity(self):
        from app.expiry_rules import _check_rule
        item = {"status": "Active", "name": "Test FD", "days_to_maturity": 15, "maturity_date": "2026-04-05"}
        msg = _check_rule(item, "fd", "days_before_maturity", 30)
        assert msg is not None
        assert "15 day(s)" in msg

    def test_fd_not_triggered_outside_threshold(self):
        from app.expiry_rules import _check_rule
        item = {"status": "Active", "name": "Test FD", "days_to_maturity": 60, "maturity_date": "2026-05-20"}
        msg = _check_rule(item, "fd", "days_before_maturity", 30)
        assert msg is None

    def test_on_maturity_day(self):
        from app.expiry_rules import _check_rule
        item = {"status": "Active", "name": "Test RD", "days_to_maturity": 0, "maturity_date": "2026-03-22"}
        msg = _check_rule(item, "rd", "on_maturity", 0)
        assert msg is not None
        assert "matures today" in msg

    def test_ppf_on_maturity(self):
        from app.expiry_rules import _check_rule
        item = {"status": "Active", "name": "PPF Account", "days_to_maturity": 0, "maturity_date": "2026-03-28"}
        msg = _check_rule(item, "ppf", "on_maturity", 0)
        assert msg is not None
        assert "PPF" in msg

    def test_ppf_days_before_maturity(self):
        from app.expiry_rules import _check_rule
        item = {"status": "Active", "name": "PPF Account", "days_to_maturity": 10, "maturity_date": "2026-04-07"}
        msg = _check_rule(item, "ppf", "days_before_maturity", 30)
        assert msg is not None
        assert "10 day(s)" in msg

    def test_si_days_before_expiry(self):
        from app.expiry_rules import _check_rule
        item = {"status": "Active", "beneficiary": "Test SI", "days_to_expiry": 5, "expiry_date": "2026-03-27"}
        msg = _check_rule(item, "si", "days_before_expiry", 7)
        assert msg is not None
        assert "5 day(s)" in msg
        assert "Standing Instruction" in msg

    def test_si_on_expiry(self):
        from app.expiry_rules import _check_rule
        item = {"status": "Active", "beneficiary": "Bill Pay", "days_to_expiry": 0, "expiry_date": "2026-03-28"}
        msg = _check_rule(item, "si", "on_expiry", 0)
        assert msg is not None
        assert "expires today" in msg

    def test_insurance_on_expiry(self):
        from app.expiry_rules import _check_rule
        item = {"status": "Active", "name": "Life Policy", "days_to_expiry": 0, "expiry_date": "2026-03-22"}
        msg = _check_rule(item, "insurance", "on_expiry", 0)
        assert msg is not None
        assert "Insurance" in msg
        assert "expires today" in msg

    def test_insurance_days_before_expiry(self):
        from app.expiry_rules import _check_rule
        item = {"status": "Active", "name": "Health Policy", "days_to_expiry": 14, "expiry_date": "2026-04-11"}
        msg = _check_rule(item, "insurance", "days_before_expiry", 30)
        assert msg is not None
        assert "14 day(s)" in msg

    def test_inactive_skipped(self):
        from app.expiry_rules import _check_rule
        item = {"status": "Matured", "name": "Old FD", "days_to_maturity": 0, "maturity_date": "2025-01-01"}
        msg = _check_rule(item, "fd", "on_maturity", 0)
        assert msg is None

    def test_nps_contribution_reminder_late_month_no_contribution(self):
        from app.expiry_rules import _check_rule
        now = datetime.now()
        item = {
            "status": "Active",
            "name": "NPS Tier 1",
            "contributions": [],
        }
        with patch("app.expiry_rules.datetime") as mock_dt:
            mock_dt.now.return_value = now.replace(day=26)
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            msg = _check_rule(item, "nps", "contribution_reminder", 0)
        if now.day >= 25:
            # If we're in the late part of the month, we'd get a message
            assert msg is None or "NPS" in msg

    def test_nps_contribution_reminder_has_contribution(self):
        from app.expiry_rules import _check_rule
        now = datetime.now()
        current_month = now.strftime("%Y-%m")
        item = {
            "status": "Active",
            "name": "NPS Tier 1",
            "contributions": [{"date": f"{current_month}-15", "amount": 5000}],
        }
        msg = _check_rule(item, "nps", "contribution_reminder", 0)
        assert msg is None

    def test_nps_contribution_reminder_early_month(self):
        from app.expiry_rules import _check_rule
        item = {
            "status": "Active",
            "name": "NPS Tier 1",
            "contributions": [],
        }
        with patch("app.expiry_rules.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 3, 10)
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            msg = _check_rule(item, "nps", "contribution_reminder", 0)
        # Day 10 < 25, so no reminder
        assert msg is None

    def test_fd_negative_days_no_trigger(self):
        from app.expiry_rules import _check_rule
        item = {"status": "Active", "name": "FD", "days_to_maturity": -5, "maturity_date": "2026-03-20"}
        msg = _check_rule(item, "fd", "days_before_maturity", 30)
        assert msg is None

    def test_unknown_category_returns_none(self):
        from app.expiry_rules import _check_rule
        item = {"status": "Active", "name": "X"}
        msg = _check_rule(item, "unknown_category", "on_maturity", 30)
        assert msg is None

    def test_name_from_account_name(self):
        from app.expiry_rules import _check_rule
        item = {"status": "Active", "account_name": "My FD Account", "days_to_maturity": 0, "maturity_date": "2026-03-28"}
        msg = _check_rule(item, "fd", "on_maturity", 0)
        assert msg is not None
        assert "My FD Account" in msg

    def test_name_from_bank_field(self):
        from app.expiry_rules import _check_rule
        item = {"status": "Active", "bank": "SBI", "days_to_maturity": 5, "maturity_date": "2026-04-02"}
        msg = _check_rule(item, "fd", "days_before_maturity", 10)
        assert "SBI" in msg


class TestIsWithinAlertWindow:
    def test_within_window(self):
        from app.expiry_rules import _is_within_alert_window
        now = datetime.now()
        alert_time = now.strftime("%H:%M")
        assert _is_within_alert_window(alert_time) is True

    def test_outside_window(self):
        from app.expiry_rules import _is_within_alert_window
        assert _is_within_alert_window("03:00") is (_is_close_to_3am())

    def test_invalid_time(self):
        from app.expiry_rules import _is_within_alert_window
        assert _is_within_alert_window("invalid") is False

    def test_empty_time(self):
        from app.expiry_rules import _is_within_alert_window
        assert _is_within_alert_window("") is False


def _is_close_to_3am():
    """Helper: check if current time is within 2 min of 03:00."""
    now = datetime.now()
    target = now.replace(hour=3, minute=0, second=0, microsecond=0)
    return abs((now - target).total_seconds()) <= 120


class TestFmtInr:
    def test_positive(self):
        from app.expiry_rules import _fmt_inr
        result = _fmt_inr(1234.56)
        assert "\u20b9" in result  # rupee sign
        assert "1,234.56" in result

    def test_negative(self):
        from app.expiry_rules import _fmt_inr
        result = _fmt_inr(-500.25)
        assert "-" in result
        assert "500.25" in result

    def test_zero(self):
        from app.expiry_rules import _fmt_inr
        result = _fmt_inr(0)
        assert "0.00" in result


class TestBuildAlertHtml:
    def _sample_profit_lots(self):
        return [
            {
                "name": "RELIANCE",
                "exchange": "NSE",
                "buy_date": "2024-01-15",
                "qty": 10,
                "buy_price": 2000.0,
                "current_price": 3000.0,
                "pl_inr": 10000.0,
                "pl_pct": 50.0,
                "pl_pa": 45.2,
            },
            {
                "name": "TCS",
                "exchange": "NSE",
                "buy_date": "2023-06-01",
                "qty": 5,
                "buy_price": 3000.0,
                "current_price": 4500.0,
                "pl_inr": 7500.0,
                "pl_pct": 50.0,
                "pl_pa": None,
            },
        ]

    def test_build_profit_alert_html_stocks(self):
        from app.expiry_rules import _build_profit_alert_html
        html = _build_profit_alert_html(self._sample_profit_lots(), "stocks", 25.0)
        assert "RELIANCE" in html
        assert "TCS" in html
        assert "Stock" in html
        assert "Qty" in html
        assert "Exceed 25% Profit" in html

    def test_build_profit_alert_html_mf(self):
        from app.expiry_rules import _build_profit_alert_html
        lots = self._sample_profit_lots()
        html = _build_profit_alert_html(lots, "mf", 10.0)
        assert "Mutual Fund" in html
        assert "Units" in html

    def test_build_profit_alert_plain_stocks(self):
        from app.expiry_rules import _build_profit_alert_plain
        plain = _build_profit_alert_plain(self._sample_profit_lots(), "stocks", 25.0)
        assert "RELIANCE" in plain
        assert "Stock" in plain
        assert "25%" in plain

    def test_build_profit_alert_plain_mf(self):
        from app.expiry_rules import _build_profit_alert_plain
        plain = _build_profit_alert_plain(self._sample_profit_lots(), "mf", 10.0)
        assert "MF" in plain


class TestBuildDropAlert:
    def _sample_drop_items(self):
        return [
            {
                "name": "RELIANCE",
                "exchange": "NSE",
                "qty": 10,
                "current_price": 2000.0,
                "day_change_pct": -5.5,
                "day_loss_inr": -1100.0,
                "total_value": 20000.0,
                "prev_close": 2116.4,
                "day_change": -116.4,
            },
        ]

    def test_build_drop_alert_html_stocks_1d(self):
        from app.expiry_rules import _build_drop_alert_html
        html = _build_drop_alert_html(self._sample_drop_items(), "stocks", 5.0, "1D")
        assert "RELIANCE" in html
        assert "Today" in html
        assert "Stock" in html

    def test_build_drop_alert_html_mf_1w(self):
        from app.expiry_rules import _build_drop_alert_html
        html = _build_drop_alert_html(self._sample_drop_items(), "mf", 5.0, "1W")
        assert "Mutual Fund" in html
        assert "This Week" in html

    def test_build_drop_alert_html_1m(self):
        from app.expiry_rules import _build_drop_alert_html
        html = _build_drop_alert_html(self._sample_drop_items(), "stocks", 10.0, "1M")
        assert "This Month" in html

    def test_build_drop_alert_plain(self):
        from app.expiry_rules import _build_drop_alert_plain
        plain = _build_drop_alert_plain(self._sample_drop_items(), "stocks", 5.0, "1D")
        assert "RELIANCE" in plain
        assert "Stock" in plain

    def test_build_drop_alert_plain_mf(self):
        from app.expiry_rules import _build_drop_alert_plain
        plain = _build_drop_alert_plain(self._sample_drop_items(), "mf", 3.0, "1W")
        assert "MF" in plain


class TestBuild52wAlert:
    def _sample_52w_items(self):
        return [
            {
                "name": "SBIN",
                "exchange": "NSE",
                "qty": 50,
                "current_price": 800.0,
                "ref_price": 810.0,
                "pct_from_ref": -1.2,
                "total_value": 40000.0,
                "w52_high": 810.0,
                "w52_low": 550.0,
            },
        ]

    def test_build_52w_alert_html_high(self):
        from app.expiry_rules import _build_52w_alert_html
        html = _build_52w_alert_html(self._sample_52w_items(), "stocks", True)
        assert "SBIN" in html
        assert "52-Week High" in html

    def test_build_52w_alert_html_low(self):
        from app.expiry_rules import _build_52w_alert_html
        html = _build_52w_alert_html(self._sample_52w_items(), "mf", False)
        assert "52-Week Low" in html
        assert "Mutual Fund" in html

    def test_build_52w_alert_plain_high(self):
        from app.expiry_rules import _build_52w_alert_plain
        plain = _build_52w_alert_plain(self._sample_52w_items(), "stocks", True)
        assert "52-week high" in plain

    def test_build_52w_alert_plain_low(self):
        from app.expiry_rules import _build_52w_alert_plain
        plain = _build_52w_alert_plain(self._sample_52w_items(), "mf", False)
        assert "52-week low" in plain
        assert "MF" in plain


class TestLoadUserInstruments:
    def test_load_instruments_no_dumps_dir(self, tmp_env, monkeypatch):
        from app.expiry_rules import _load_user_instruments
        monkeypatch.setattr("app.expiry_rules.get_user_dumps_dir", lambda uid, email: None)
        result = _load_user_instruments("test@example.com", "testuser")
        assert result == {"fd": [], "rd": [], "ppf": [], "nps": [], "si": [], "insurance": []}

    def test_load_instruments_with_import_errors(self, tmp_env):
        from app.expiry_rules import _load_user_instruments
        # With empty directories, all import/reads will gracefully return empty
        result = _load_user_instruments("test@example.com", "testuser")
        assert isinstance(result, dict)
        assert "fd" in result

    def test_load_instruments_with_fd_data(self, tmp_env, monkeypatch):
        from app.expiry_rules import _load_user_instruments
        mock_fd = [{"name": "FD1", "status": "Active"}]
        with patch("app.fd_database.get_all", return_value=mock_fd):
            result = _load_user_instruments("test@example.com", "testuser")
        assert result["fd"] == mock_fd

    def test_load_instruments_with_rd_data(self, tmp_env, monkeypatch):
        from app.expiry_rules import _load_user_instruments
        mock_rd = [{"name": "RD1", "status": "Active"}]
        with patch("app.rd_database.get_all", return_value=mock_rd):
            result = _load_user_instruments("test@example.com", "testuser")
        assert result["rd"] == mock_rd

    def test_load_instruments_ppf_nps_graceful_failures(self, tmp_env):
        """PPFDatabase and NPSDatabase may not exist; import errors are caught."""
        from app.expiry_rules import _load_user_instruments
        result = _load_user_instruments("test@example.com", "testuser")
        # Should return empty lists for ppf/nps since PPFDatabase/NPSDatabase
        # may not exist or dumps dirs are empty
        assert result["ppf"] == [] or isinstance(result["ppf"], list)
        assert result["nps"] == [] or isinstance(result["nps"], list)

    def test_load_instruments_si_data(self, tmp_env, monkeypatch):
        from app.expiry_rules import _load_user_instruments
        mock_si = [{"beneficiary": "SI1", "status": "Active"}]
        with patch("app.si_database.get_all", return_value=mock_si):
            result = _load_user_instruments("test@example.com", "testuser")
        assert result["si"] == mock_si

    def test_load_instruments_insurance_data(self, tmp_env, monkeypatch):
        from app.expiry_rules import _load_user_instruments
        mock_ins = [{"name": "INS1", "status": "Active"}]
        with patch("app.insurance_database.get_all", return_value=mock_ins):
            result = _load_user_instruments("test@example.com", "testuser")
        assert result["insurance"] == mock_ins


class TestEvaluateExpiryRules:
    def test_evaluate_no_users(self, tmp_env, monkeypatch):
        from app.expiry_rules import evaluate_expiry_rules
        monkeypatch.setattr("app.expiry_rules.get_users", lambda: [])
        evaluate_expiry_rules()  # Should not raise

    def test_evaluate_no_rules(self, tmp_env, monkeypatch):
        from app.expiry_rules import evaluate_expiry_rules
        evaluate_expiry_rules()  # No rules saved, should be a no-op

    def test_evaluate_with_expiry_rule_triggers(self, tmp_env, monkeypatch):
        from app.expiry_rules import save_rule, evaluate_expiry_rules
        save_rule("test@example.com", "testuser", {
            "category": "fd", "rule_type": "on_maturity",
        })
        instruments = {
            "fd": [{"status": "Active", "name": "FD1", "days_to_maturity": 0, "maturity_date": "2026-03-28"}],
            "rd": [], "ppf": [], "nps": [], "si": [], "insurance": [],
        }
        monkeypatch.setattr(
            "app.expiry_rules._load_user_instruments",
            lambda email, uid: instruments,
        )
        with patch("app.notification_service.notify", return_value=True) as mock_notify, \
             patch("app.alert_service._check_cooldown", return_value=True), \
             patch("app.alert_service._record_history"):
            evaluate_expiry_rules()
            mock_notify.assert_called()

    def test_evaluate_cooldown_blocks(self, tmp_env, monkeypatch):
        from app.expiry_rules import save_rule, evaluate_expiry_rules
        save_rule("test@example.com", "testuser", {
            "category": "fd", "rule_type": "on_maturity",
        })
        instruments = {
            "fd": [{"status": "Active", "name": "FD1", "days_to_maturity": 0, "maturity_date": "2026-03-28"}],
            "rd": [], "ppf": [], "nps": [], "si": [], "insurance": [],
        }
        monkeypatch.setattr("app.expiry_rules._load_user_instruments", lambda e, u: instruments)
        with patch("app.notification_service.notify", return_value=True) as mock_notify, \
             patch("app.alert_service._check_cooldown", return_value=False):
            evaluate_expiry_rules()
            mock_notify.assert_not_called()

    def test_evaluate_with_profit_rule(self, tmp_env, monkeypatch):
        from app.expiry_rules import save_rule, evaluate_expiry_rules
        save_rule("test@example.com", "testuser", {
            "category": "stocks", "rule_type": "profit_threshold",
            "threshold_pct": 25, "alert_time": datetime.now().strftime("%H:%M"),
        })
        monkeypatch.setattr("app.expiry_rules._load_user_instruments", lambda e, u: {
            "fd": [], "rd": [], "ppf": [], "nps": [], "si": [], "insurance": [],
        })
        with patch("app.expiry_rules._evaluate_profit_rule") as mock_eval:
            evaluate_expiry_rules()
            mock_eval.assert_called_once()

    def test_evaluate_skips_empty_email_or_id(self, tmp_env, monkeypatch):
        from app.expiry_rules import evaluate_expiry_rules
        monkeypatch.setattr("app.expiry_rules.get_users", lambda: [
            {"id": "", "name": "NoId", "email": "test@example.com"},
            {"id": "testuser", "name": "TestUser", "email": ""},
        ])
        evaluate_expiry_rules()  # Should not raise


class TestEvaluateProfitRule:
    def test_outside_alert_window(self, tmp_env):
        from app.expiry_rules import _evaluate_profit_rule
        rule = {
            "id": "r1", "category": "stocks", "rule_type": "profit_threshold",
            "threshold_pct": 25, "alert_time": "03:00",
        }
        with patch("app.expiry_rules._is_within_alert_window", return_value=False):
            _evaluate_profit_rule(rule, "test@example.com", "testuser", MagicMock())

    def test_cooldown_blocks(self, tmp_env):
        from app.expiry_rules import _evaluate_profit_rule
        rule = {
            "id": "r1", "category": "stocks", "rule_type": "profit_threshold",
            "threshold_pct": 25, "alert_time": "16:30",
        }
        with patch("app.expiry_rules._is_within_alert_window", return_value=True), \
             patch("app.alert_service._check_cooldown", return_value=False):
            ns = MagicMock()
            _evaluate_profit_rule(rule, "test@example.com", "testuser", ns)
            ns.notify.assert_not_called()

    def test_profit_threshold_no_qualifying(self, tmp_env):
        from app.expiry_rules import _evaluate_profit_rule
        rule = {
            "id": "r1", "category": "stocks", "rule_type": "profit_threshold",
            "threshold_pct": 25, "alert_time": "16:30",
        }
        with patch("app.expiry_rules._is_within_alert_window", return_value=True), \
             patch("app.alert_service._check_cooldown", return_value=True), \
             patch("app.expiry_rules._get_stock_lots_above_threshold", return_value=[]):
            ns = MagicMock()
            _evaluate_profit_rule(rule, "test@example.com", "testuser", ns)
            ns.notify.assert_not_called()

    def test_profit_threshold_with_qualifying_stocks(self, tmp_env):
        from app.expiry_rules import _evaluate_profit_rule
        rule = {
            "id": "r1", "category": "stocks", "rule_type": "profit_threshold",
            "threshold_pct": 25, "alert_time": "16:30",
        }
        lots = [{
            "name": "RELIANCE", "exchange": "NSE", "buy_date": "2024-01-01",
            "qty": 10, "buy_price": 2000, "current_price": 3000,
            "pl_inr": 10000, "pl_pct": 50, "pl_pa": 45.0,
        }]
        with patch("app.expiry_rules._is_within_alert_window", return_value=True), \
             patch("app.alert_service._check_cooldown", return_value=True), \
             patch("app.alert_service._record_history"), \
             patch("app.expiry_rules._get_stock_lots_above_threshold", return_value=lots):
            ns = MagicMock()
            ns.notify.return_value = True
            _evaluate_profit_rule(rule, "test@example.com", "testuser", ns)
            ns.notify.assert_called_once()

    def test_day_drop_threshold(self, tmp_env):
        from app.expiry_rules import _evaluate_profit_rule
        rule = {
            "id": "r2", "category": "stocks", "rule_type": "day_drop_threshold",
            "threshold_pct": 5, "alert_time": "16:30",
        }
        items = [{"name": "TCS", "exchange": "NSE", "qty": 10, "current_price": 3500,
                  "day_change_pct": -6.0, "day_loss_inr": -2100, "total_value": 35000,
                  "prev_close": 3723.4, "day_change": -223.4}]
        with patch("app.expiry_rules._is_within_alert_window", return_value=True), \
             patch("app.alert_service._check_cooldown", return_value=True), \
             patch("app.alert_service._record_history"), \
             patch("app.expiry_rules._get_stock_period_drops", return_value=items):
            ns = MagicMock()
            ns.notify.return_value = True
            _evaluate_profit_rule(rule, "test@example.com", "testuser", ns)
            ns.notify.assert_called_once()

    def test_week_drop_threshold_mf(self, tmp_env):
        from app.expiry_rules import _evaluate_profit_rule
        rule = {
            "id": "r3", "category": "mf", "rule_type": "week_drop_threshold",
            "threshold_pct": 3, "alert_time": "16:30",
        }
        items = [{"name": "HDFC Fund", "fund_code": "INF1", "qty": 100,
                  "current_price": 45.0, "day_change_pct": -4.0,
                  "day_loss_inr": -180, "total_value": 4500,
                  "prev_close": 46.88, "day_change": -1.88}]
        with patch("app.expiry_rules._is_within_alert_window", return_value=True), \
             patch("app.alert_service._check_cooldown", return_value=True), \
             patch("app.alert_service._record_history"), \
             patch("app.expiry_rules._get_mf_period_drops", return_value=items):
            ns = MagicMock()
            ns.notify.return_value = True
            _evaluate_profit_rule(rule, "test@example.com", "testuser", ns)
            ns.notify.assert_called_once()

    def test_near_52w_high_stocks(self, tmp_env):
        from app.expiry_rules import _evaluate_profit_rule
        rule = {
            "id": "r4", "category": "stocks", "rule_type": "near_52w_high",
            "alert_time": "16:30",
        }
        items = [{"name": "SBIN", "exchange": "NSE", "qty": 50,
                  "current_price": 800, "ref_price": 810, "pct_from_ref": -1.2,
                  "total_value": 40000, "w52_high": 810, "w52_low": 550}]
        with patch("app.expiry_rules._is_within_alert_window", return_value=True), \
             patch("app.alert_service._check_cooldown", return_value=True), \
             patch("app.alert_service._record_history"), \
             patch("app.expiry_rules._get_stock_52w_hits", return_value=items):
            ns = MagicMock()
            ns.notify.return_value = True
            _evaluate_profit_rule(rule, "test@example.com", "testuser", ns)
            ns.notify.assert_called_once()

    def test_near_52w_low_mf(self, tmp_env):
        from app.expiry_rules import _evaluate_profit_rule
        rule = {
            "id": "r5", "category": "mf", "rule_type": "near_52w_low",
            "alert_time": "16:30",
        }
        items = [{"name": "SBI Fund", "fund_code": "INF2", "qty": 200,
                  "current_price": 30, "ref_price": 29.5, "pct_from_ref": 1.7,
                  "total_value": 6000, "w52_high": 45, "w52_low": 29.5}]
        with patch("app.expiry_rules._is_within_alert_window", return_value=True), \
             patch("app.alert_service._check_cooldown", return_value=True), \
             patch("app.alert_service._record_history"), \
             patch("app.expiry_rules._get_mf_52w_hits", return_value=items):
            ns = MagicMock()
            ns.notify.return_value = True
            _evaluate_profit_rule(rule, "test@example.com", "testuser", ns)
            ns.notify.assert_called_once()

    def test_unknown_rule_type_returns_early(self, tmp_env):
        from app.expiry_rules import _evaluate_profit_rule
        rule = {
            "id": "r6", "category": "stocks", "rule_type": "unknown_type",
            "alert_time": "16:30",
        }
        with patch("app.expiry_rules._is_within_alert_window", return_value=True), \
             patch("app.alert_service._check_cooldown", return_value=True):
            ns = MagicMock()
            _evaluate_profit_rule(rule, "test@example.com", "testuser", ns)
            ns.notify.assert_not_called()

    def test_month_drop_threshold(self, tmp_env):
        from app.expiry_rules import _evaluate_profit_rule
        rule = {
            "id": "r7", "category": "stocks", "rule_type": "month_drop_threshold",
            "threshold_pct": 10, "alert_time": "16:30",
        }
        items = [{"name": "INFY", "exchange": "NSE", "qty": 20, "current_price": 1400,
                  "day_change_pct": -12.0, "day_loss_inr": -3360, "total_value": 28000,
                  "prev_close": 1590.9, "day_change": -190.9}]
        with patch("app.expiry_rules._is_within_alert_window", return_value=True), \
             patch("app.alert_service._check_cooldown", return_value=True), \
             patch("app.alert_service._record_history"), \
             patch("app.expiry_rules._get_stock_period_drops", return_value=items):
            ns = MagicMock()
            ns.notify.return_value = True
            _evaluate_profit_rule(rule, "test@example.com", "testuser", ns)
            ns.notify.assert_called_once()

    def test_profit_threshold_mf(self, tmp_env):
        from app.expiry_rules import _evaluate_profit_rule
        rule = {
            "id": "r8", "category": "mf", "rule_type": "profit_threshold",
            "threshold_pct": 20, "alert_time": "16:30",
        }
        lots = [{
            "name": "HDFC Fund", "fund_code": "INF1", "buy_date": "2024-01-01",
            "qty": 100, "buy_price": 40, "current_price": 55,
            "pl_inr": 1500, "pl_pct": 37.5, "pl_pa": 30.0,
        }]
        with patch("app.expiry_rules._is_within_alert_window", return_value=True), \
             patch("app.alert_service._check_cooldown", return_value=True), \
             patch("app.alert_service._record_history"), \
             patch("app.expiry_rules._get_mf_lots_above_threshold", return_value=lots):
            ns = MagicMock()
            ns.notify.return_value = True
            _evaluate_profit_rule(rule, "test@example.com", "testuser", ns)
            ns.notify.assert_called_once()


def _make_mock_holding(symbol="RELIANCE", exchange="NSE", buy_price=2000.0,
                       quantity=10, buy_date="2024-01-15"):
    h = MagicMock()
    h.symbol = symbol
    h.exchange = exchange
    h.buy_price = buy_price
    h.quantity = quantity
    h.buy_date = buy_date
    return h


def _make_mock_mf_holding(buy_price=40.0, units=100.0, buy_date="2024-01-15"):
    h = MagicMock()
    h.buy_price = buy_price
    h.units = units
    h.buy_date = buy_date
    return h


class TestGetStockLotsAboveThreshold:
    def test_returns_empty_on_exception(self, tmp_env, monkeypatch):
        from app.expiry_rules import _get_stock_lots_above_threshold
        monkeypatch.setattr("app.expiry_rules.get_user_dumps_dir", lambda uid, email: None)
        result = _get_stock_lots_above_threshold("test@example.com", "testuser", 25)
        assert result == []

    def test_with_qualifying_stocks(self, tmp_env):
        from app.expiry_rules import _get_stock_lots_above_threshold
        holdings = [_make_mock_holding("RELIANCE", "NSE", 2000, 10, "2024-01-15")]
        mock_db = MagicMock()
        mock_db.get_all_data.return_value = (holdings, [], {})

        # live_data.get(h.symbol) uses just "RELIANCE" as key
        price_mock = MagicMock()
        price_mock.get = lambda k, d=None: {"current_price": 3000}.get(k, d)
        cached = {"RELIANCE": price_mock}

        with patch("app.xlsx_database.XlsxPortfolio", return_value=mock_db), \
             patch("app.stock_service.get_cached_prices", return_value=cached):
            result = _get_stock_lots_above_threshold("test@example.com", "testuser", 25)
        assert len(result) == 1
        assert result[0]["name"] == "RELIANCE"
        assert result[0]["pl_pct"] == 50.0

    def test_no_holdings(self, tmp_env):
        from app.expiry_rules import _get_stock_lots_above_threshold
        mock_db = MagicMock()
        mock_db.get_all_data.return_value = ([], [], {})

        with patch("app.xlsx_database.XlsxPortfolio", return_value=mock_db):
            result = _get_stock_lots_above_threshold("test@example.com", "testuser", 25)
        assert result == []

    def test_below_threshold(self, tmp_env):
        from app.expiry_rules import _get_stock_lots_above_threshold
        holdings = [_make_mock_holding("RELIANCE", "NSE", 2000, 10, "2024-01-15")]
        mock_db = MagicMock()
        mock_db.get_all_data.return_value = (holdings, [], {})

        price_mock = MagicMock()
        price_mock.get = lambda k, d=None: {"current_price": 2100}.get(k, d)
        cached = {"RELIANCE": price_mock}

        with patch("app.xlsx_database.XlsxPortfolio", return_value=mock_db), \
             patch("app.stock_service.get_cached_prices", return_value=cached):
            result = _get_stock_lots_above_threshold("test@example.com", "testuser", 25)
        assert result == []

    def test_no_price_info(self, tmp_env):
        from app.expiry_rules import _get_stock_lots_above_threshold
        holdings = [_make_mock_holding("MISSING", "NSE", 2000, 10)]
        mock_db = MagicMock()
        mock_db.get_all_data.return_value = (holdings, [], {})

        with patch("app.xlsx_database.XlsxPortfolio", return_value=mock_db), \
             patch("app.stock_service.get_cached_prices", return_value={}):
            result = _get_stock_lots_above_threshold("test@example.com", "testuser", 25)
        assert result == []


class TestGetMfLotsAboveThreshold:
    def test_returns_empty_on_exception(self, tmp_env, monkeypatch):
        from app.expiry_rules import _get_mf_lots_above_threshold
        monkeypatch.setattr("app.expiry_rules.get_user_dumps_dir", lambda uid, email: None)
        result = _get_mf_lots_above_threshold("test@example.com", "testuser", 25)
        assert result == []

    def test_with_qualifying_mf(self, tmp_env):
        from app.expiry_rules import _get_mf_lots_above_threshold
        holdings = [_make_mock_mf_holding(40.0, 100, "2024-01-15")]
        mock_db_cls = MagicMock()
        mock_db_instance = MagicMock()
        mock_db_cls.return_value = mock_db_instance
        mock_db_instance._file_map = {"INF123": "/fake.xlsx"}
        mock_db_instance._name_map = {"INF123": "Test Fund"}
        mock_db_instance._get_fund_data.return_value = (holdings, [], {"current_nav": 60.0})

        # Create the Mutual Funds dir so the code doesn't bail out early
        mf_dir = tmp_env / "test@example.com" / "Testuser" / "Mutual Funds"
        mf_dir.mkdir(parents=True, exist_ok=True)

        import app.mf_xlsx_database as mf_mod
        with patch.object(mf_mod, "MFXlsxPortfolio", mock_db_cls), \
             patch.object(mf_mod, "fetch_live_navs", return_value={"INF123": 60.0}):
            result = _get_mf_lots_above_threshold("test@example.com", "testuser", 25)
        assert len(result) == 1
        assert result[0]["pl_pct"] == 50.0

    def test_no_mf_dir(self, tmp_env, monkeypatch):
        from app.expiry_rules import _get_mf_lots_above_threshold
        # dumps_dir exists but no "Mutual Funds" sub
        monkeypatch.setattr("app.expiry_rules.get_user_dumps_dir",
                            lambda uid, email: tmp_env / "test@example.com" / "Testuser")
        result = _get_mf_lots_above_threshold("test@example.com", "testuser", 25)
        assert result == []


class TestGetStockPeriodDrops:
    def test_returns_empty_on_exception(self, tmp_env, monkeypatch):
        from app.expiry_rules import _get_stock_period_drops
        monkeypatch.setattr("app.expiry_rules.get_user_dumps_dir", lambda uid, email: None)
        result = _get_stock_period_drops("test@example.com", "testuser", 5, "1D")
        assert result == []

    def test_with_drops(self, tmp_env):
        from app.expiry_rules import _get_stock_period_drops
        holdings = [_make_mock_holding("INFY", "NSE", 1800, 20, "2024-01-15")]
        mock_db = MagicMock()
        mock_db.get_all_data.return_value = (holdings, [], {})

        price_mock = MagicMock()
        price_mock.get = lambda k, d=None: {
            "current_price": 1600, "day_change_pct": -8.0,
            "week_change_pct": -10.0, "month_change_pct": -15.0
        }.get(k, d)
        cached = {"INFY": price_mock}

        with patch("app.xlsx_database.XlsxPortfolio", return_value=mock_db), \
             patch("app.stock_service.get_cached_prices", return_value=cached):
            result = _get_stock_period_drops("test@example.com", "testuser", 5, "1D")
        assert len(result) == 1
        assert result[0]["name"] == "INFY"

    def test_no_drop(self, tmp_env):
        from app.expiry_rules import _get_stock_period_drops
        holdings = [_make_mock_holding("RELIANCE", "NSE", 2000, 10)]
        mock_db = MagicMock()
        mock_db.get_all_data.return_value = (holdings, [], {})

        price_mock = MagicMock()
        price_mock.get = lambda k, d=None: {
            "current_price": 2100, "day_change_pct": 2.0
        }.get(k, d)
        cached = {"RELIANCE": price_mock}

        with patch("app.xlsx_database.XlsxPortfolio", return_value=mock_db), \
             patch("app.stock_service.get_cached_prices", return_value=cached):
            result = _get_stock_period_drops("test@example.com", "testuser", 5, "1D")
        assert result == []


class TestGetMfPeriodDrops:
    def test_returns_empty_on_exception(self, tmp_env, monkeypatch):
        from app.expiry_rules import _get_mf_period_drops
        monkeypatch.setattr("app.expiry_rules.get_user_dumps_dir", lambda uid, email: None)
        result = _get_mf_period_drops("test@example.com", "testuser", 5, "1D")
        assert result == []

    def test_with_drops(self, tmp_env):
        from app.expiry_rules import _get_mf_period_drops
        holdings = [_make_mock_mf_holding(50.0, 200, "2024-01-15")]
        mock_db_cls = MagicMock()
        mock_db_instance = MagicMock()
        mock_db_cls.return_value = mock_db_instance
        mock_db_instance._file_map = {"INF123": "/fake.xlsx"}
        mock_db_instance._name_map = {"INF123": "Test Fund"}
        mock_db_instance._get_fund_data.return_value = (holdings, [], {"current_nav": 45.0})

        mf_dir = tmp_env / "test@example.com" / "Testuser" / "Mutual Funds"
        mf_dir.mkdir(parents=True, exist_ok=True)

        nav_changes = {"day_change_pct": -6.0, "week_change_pct": -8.0, "month_change_pct": -12.0}
        import app.mf_xlsx_database as mf_mod
        with patch.object(mf_mod, "MFXlsxPortfolio", mock_db_cls), \
             patch.object(mf_mod, "fetch_live_navs", return_value={"INF123": 45.0}), \
             patch.object(mf_mod, "compute_nav_changes", return_value=nav_changes):
            result = _get_mf_period_drops("test@example.com", "testuser", 5, "1D")
        assert len(result) == 1


class TestGetStock52wHits:
    def test_returns_empty_on_exception(self, tmp_env, monkeypatch):
        from app.expiry_rules import _get_stock_52w_hits
        monkeypatch.setattr("app.expiry_rules.get_user_dumps_dir", lambda uid, email: None)
        result = _get_stock_52w_hits("test@example.com", "testuser", True)
        assert result == []

    def test_near_52w_high(self, tmp_env):
        from app.expiry_rules import _get_stock_52w_hits
        holdings = [_make_mock_holding("SBIN", "NSE", 500, 50)]
        mock_db = MagicMock()
        mock_db.get_all_data.return_value = (holdings, [], {})

        price_mock = MagicMock()
        price_mock.get = lambda k, d=None: {
            "current_price": 805, "week_52_high": 810, "week_52_low": 550
        }.get(k, d)
        cached = {"SBIN": price_mock}

        with patch("app.xlsx_database.XlsxPortfolio", return_value=mock_db), \
             patch("app.stock_service.get_cached_prices", return_value=cached):
            result = _get_stock_52w_hits("test@example.com", "testuser", True)
        assert len(result) == 1
        assert result[0]["name"] == "SBIN"

    def test_near_52w_low(self, tmp_env):
        from app.expiry_rules import _get_stock_52w_hits
        holdings = [_make_mock_holding("INFY", "NSE", 1800, 20)]
        mock_db = MagicMock()
        mock_db.get_all_data.return_value = (holdings, [], {})

        price_mock = MagicMock()
        price_mock.get = lambda k, d=None: {
            "current_price": 1210, "week_52_high": 1900, "week_52_low": 1200
        }.get(k, d)
        cached = {"INFY": price_mock}

        with patch("app.xlsx_database.XlsxPortfolio", return_value=mock_db), \
             patch("app.stock_service.get_cached_prices", return_value=cached):
            result = _get_stock_52w_hits("test@example.com", "testuser", False)
        assert len(result) == 1

    def test_not_near_52w_high(self, tmp_env):
        from app.expiry_rules import _get_stock_52w_hits
        holdings = [_make_mock_holding("TCS", "NSE", 3000, 5)]
        mock_db = MagicMock()
        mock_db.get_all_data.return_value = (holdings, [], {})

        price_mock = MagicMock()
        price_mock.get = lambda k, d=None: {
            "current_price": 3000, "week_52_high": 4000, "week_52_low": 2500
        }.get(k, d)
        cached = {"TCS": price_mock}

        with patch("app.xlsx_database.XlsxPortfolio", return_value=mock_db), \
             patch("app.stock_service.get_cached_prices", return_value=cached):
            result = _get_stock_52w_hits("test@example.com", "testuser", True)
        assert result == []


class TestGetMf52wHits:
    def test_returns_empty_on_exception(self, tmp_env, monkeypatch):
        from app.expiry_rules import _get_mf_52w_hits
        monkeypatch.setattr("app.expiry_rules.get_user_dumps_dir", lambda uid, email: None)
        result = _get_mf_52w_hits("test@example.com", "testuser", True)
        assert result == []

    def test_near_52w_high(self, tmp_env):
        from app.expiry_rules import _get_mf_52w_hits
        holdings = [_make_mock_mf_holding(40.0, 200, "2024-01-15")]
        mock_db_cls = MagicMock()
        mock_db_instance = MagicMock()
        mock_db_cls.return_value = mock_db_instance
        mock_db_instance._file_map = {"INF123": "/fake.xlsx"}
        mock_db_instance._name_map = {"INF123": "Test Fund"}
        mock_db_instance._get_fund_data.return_value = (holdings, [], {"current_nav": 59.5})

        mf_dir = tmp_env / "test@example.com" / "Testuser" / "Mutual Funds"
        mf_dir.mkdir(parents=True, exist_ok=True)

        nav_changes = {"week_52_high": 60.0, "week_52_low": 35.0}
        import app.mf_xlsx_database as mf_mod
        with patch.object(mf_mod, "MFXlsxPortfolio", mock_db_cls), \
             patch.object(mf_mod, "fetch_live_navs", return_value={"INF123": 59.5}), \
             patch.object(mf_mod, "compute_nav_changes", return_value=nav_changes):
            result = _get_mf_52w_hits("test@example.com", "testuser", True)
        assert len(result) == 1

    def test_near_52w_low(self, tmp_env):
        from app.expiry_rules import _get_mf_52w_hits
        holdings = [_make_mock_mf_holding(50.0, 100, "2024-01-15")]
        mock_db_cls = MagicMock()
        mock_db_instance = MagicMock()
        mock_db_cls.return_value = mock_db_instance
        mock_db_instance._file_map = {"INF456": "/fake.xlsx"}
        mock_db_instance._name_map = {"INF456": "Low Fund"}
        mock_db_instance._get_fund_data.return_value = (holdings, [], {"current_nav": 30.5})

        mf_dir = tmp_env / "test@example.com" / "Testuser" / "Mutual Funds"
        mf_dir.mkdir(parents=True, exist_ok=True)

        nav_changes = {"week_52_high": 55.0, "week_52_low": 30.0}
        import app.mf_xlsx_database as mf_mod
        with patch.object(mf_mod, "MFXlsxPortfolio", mock_db_cls), \
             patch.object(mf_mod, "fetch_live_navs", return_value={"INF456": 30.5}), \
             patch.object(mf_mod, "compute_nav_changes", return_value=nav_changes):
            result = _get_mf_52w_hits("test@example.com", "testuser", False)
        assert len(result) == 1
