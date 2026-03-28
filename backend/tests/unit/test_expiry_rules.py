"""Tests for expiry_rules module."""
import json
from unittest.mock import patch

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
    return dumps


class TestRuleTypes:
    def test_all_categories_present(self):
        from app.expiry_rules import RULE_TYPES
        for cat in ["fd", "rd", "ppf", "nps", "si", "insurance"]:
            assert cat in RULE_TYPES, f"Missing category: {cat}"

    def test_fd_rule_types(self):
        from app.expiry_rules import RULE_TYPES
        types = [r["type"] for r in RULE_TYPES["fd"]]
        assert "days_before_maturity" in types
        assert "on_maturity" in types


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

    def test_si_days_before_expiry(self):
        from app.expiry_rules import _check_rule
        item = {"status": "Active", "beneficiary": "Test SI", "days_to_expiry": 5, "expiry_date": "2026-03-27"}
        msg = _check_rule(item, "si", "days_before_expiry", 7)
        assert msg is not None
        assert "5 day(s)" in msg

    def test_insurance_on_expiry(self):
        from app.expiry_rules import _check_rule
        item = {"status": "Active", "name": "Life Policy", "days_to_expiry": 0, "expiry_date": "2026-03-22"}
        msg = _check_rule(item, "insurance", "on_expiry", 0)
        assert msg is not None
        assert "Insurance" in msg
        assert "expires today" in msg

    def test_inactive_skipped(self):
        from app.expiry_rules import _check_rule
        item = {"status": "Matured", "name": "Old FD", "days_to_maturity": 0, "maturity_date": "2025-01-01"}
        msg = _check_rule(item, "fd", "on_maturity", 0)
        assert msg is None
