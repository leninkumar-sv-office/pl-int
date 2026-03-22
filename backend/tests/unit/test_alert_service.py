"""Tests for alert_service module."""
import json
from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture
def tmp_env(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    monkeypatch.setattr("app.alert_service._DATA_DIR", data_dir)
    monkeypatch.setattr("app.alert_service._ALERTS_FILE", data_dir / "alerts.json")
    monkeypatch.setattr("app.alert_service._HISTORY_FILE", data_dir / "alert_history.json")
    return data_dir


class TestAlertCRUD:
    def test_create_alert(self, tmp_env):
        from app.alert_service import create_or_update_alert, get_alerts
        with patch("app.alert_service._save_alerts") as mock_save:
            mock_save.side_effect = lambda alerts: (tmp_env / "alerts.json").write_text(json.dumps(alerts))
            alert = create_or_update_alert({
                "name": "Test Alert", "channel": "email",
                "condition": {"type": "test"}, "cooldown_minutes": 30,
            })
        assert alert["id"]
        assert alert["name"] == "Test Alert"
        assert alert["channel"] == "email"
        assert alert["enabled"] is True

    def test_delete_alert(self, tmp_env):
        from app.alert_service import create_or_update_alert, delete_alert, get_alerts
        # Seed a rule
        (tmp_env / "alerts.json").write_text(json.dumps([
            {"id": "abc123", "name": "X", "enabled": True, "channel": "email",
             "condition": {}, "cooldown_minutes": 60}
        ]))
        with patch("app.alert_service._save_alerts") as mock_save:
            mock_save.side_effect = lambda alerts: (tmp_env / "alerts.json").write_text(json.dumps(alerts))
            assert delete_alert("abc123") is True
            assert delete_alert("nonexistent") is False

    def test_get_history_empty(self, tmp_env):
        from app.alert_service import get_history
        assert get_history() == []

    def test_record_and_get_history(self, tmp_env):
        from app.alert_service import _record_history, get_history
        with patch("app.alert_service._save_history") as mock_save:
            mock_save.side_effect = lambda h: (tmp_env / "alert_history.json").write_text(json.dumps(h))
            _record_history("rule1", "Test", "email", "msg", True)
        history = get_history()
        assert len(history) == 1
        assert history[0]["alert_name"] == "Test"
        assert history[0]["success"] is True


class TestCooldown:
    def test_cooldown_allows_first_notification(self, tmp_env):
        from app.alert_service import _check_cooldown
        assert _check_cooldown("new_rule", 60) is True

    def test_cooldown_blocks_recent(self, tmp_env):
        from app.alert_service import _check_cooldown, _record_history
        from datetime import datetime
        # Write a recent history entry
        (tmp_env / "alert_history.json").write_text(json.dumps([{
            "id": "h1", "alert_id": "rule1", "alert_name": "X",
            "channel": "email", "message": "test", "success": True,
            "timestamp": datetime.now().isoformat(),
        }]))
        assert _check_cooldown("rule1", 60) is False


class TestSendTestNotification:
    def test_send_test(self, tmp_env):
        from app.alert_service import send_test_notification
        with patch("app.alert_service.notification_service") as mock_ns:
            mock_ns.notify.return_value = True
            mock_ns.get_channel_status.return_value = {"email": {"configured": True}, "telegram": {"configured": False}}
            result = send_test_notification("email", "hello")
        assert result["success"] is True
        assert result["channel"] == "email"


class TestEvaluatorRegistry:
    def test_register_and_lookup(self, tmp_env):
        from app.alert_service import register_evaluator, _condition_evaluators
        fn = lambda cond: (True, "triggered")
        register_evaluator("test_type", fn)
        assert "test_type" in _condition_evaluators
        assert _condition_evaluators["test_type"]({})[0] is True
        # Cleanup
        del _condition_evaluators["test_type"]
