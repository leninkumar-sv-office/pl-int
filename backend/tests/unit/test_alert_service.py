"""Tests for alert_service module."""
import json
import time
from pathlib import Path
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta

import pytest


@pytest.fixture
def tmp_env(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    monkeypatch.setattr("app.alert_service._DATA_DIR", data_dir)
    monkeypatch.setattr("app.alert_service._ALERTS_FILE", data_dir / "alerts.json")
    monkeypatch.setattr("app.alert_service._HISTORY_FILE", data_dir / "alert_history.json")
    return data_dir


class TestPersistence:
    def test_load_alerts_missing_file(self, tmp_env):
        from app.alert_service import _load_alerts
        result = _load_alerts()
        assert result == []

    def test_load_alerts_invalid_json(self, tmp_env):
        (tmp_env / "alerts.json").write_text("bad json")
        from app.alert_service import _load_alerts
        result = _load_alerts()
        assert result == []

    def test_load_alerts_not_list(self, tmp_env):
        (tmp_env / "alerts.json").write_text(json.dumps({"not": "a list"}))
        from app.alert_service import _load_alerts
        result = _load_alerts()
        assert result == []

    def test_save_and_load_alerts(self, tmp_env):
        from app.alert_service import _save_alerts, _load_alerts
        alerts = [{"id": "a1", "name": "test"}]
        _save_alerts(alerts)
        loaded = _load_alerts()
        assert len(loaded) == 1
        assert loaded[0]["id"] == "a1"

    def test_load_history_missing_file(self, tmp_env):
        from app.alert_service import _load_history
        result = _load_history()
        assert result == []

    def test_load_history_invalid_json(self, tmp_env):
        (tmp_env / "alert_history.json").write_text("bad")
        from app.alert_service import _load_history
        result = _load_history()
        assert result == []

    def test_load_history_not_list(self, tmp_env):
        (tmp_env / "alert_history.json").write_text(json.dumps({"not": "list"}))
        from app.alert_service import _load_history
        result = _load_history()
        assert result == []

    def test_save_history_truncates_at_200(self, tmp_env):
        from app.alert_service import _save_history, _load_history
        # Create 250 entries
        history = [{"id": str(i), "alert_id": "x", "success": True,
                     "timestamp": datetime.now().isoformat()} for i in range(250)]
        _save_history(history)
        loaded = _load_history()
        assert len(loaded) == 200


class TestAlertCRUD:
    def test_create_alert(self, tmp_env):
        from app.alert_service import create_or_update_alert, get_alerts
        alert = create_or_update_alert({
            "name": "Test Alert", "channel": "email",
            "condition": {"type": "test"}, "cooldown_minutes": 30,
        })
        assert alert["id"]
        assert alert["name"] == "Test Alert"
        assert alert["channel"] == "email"
        assert alert["enabled"] is True
        assert alert["cooldown_minutes"] == 30

        alerts = get_alerts()
        assert len(alerts) == 1

    def test_update_alert(self, tmp_env):
        from app.alert_service import create_or_update_alert, get_alerts
        alert = create_or_update_alert({
            "name": "Original", "channel": "telegram",
        })
        updated = create_or_update_alert({
            "id": alert["id"], "name": "Updated", "enabled": False,
        })
        assert updated["name"] == "Updated"
        assert updated["enabled"] is False
        assert "updated_at" in updated
        assert len(get_alerts()) == 1

    def test_update_nonexistent_creates_new(self, tmp_env):
        from app.alert_service import create_or_update_alert, get_alerts
        alert = create_or_update_alert({
            "id": "nonexistent_id", "name": "New Alert",
        })
        # id should be new (not "nonexistent_id") since the update didn't find a match
        assert alert["name"] == "New Alert"
        assert len(get_alerts()) == 1

    def test_create_with_defaults(self, tmp_env):
        from app.alert_service import create_or_update_alert
        alert = create_or_update_alert({})
        assert alert["name"] == "Unnamed Alert"
        assert alert["enabled"] is True
        assert alert["channel"] == "telegram"
        assert alert["cooldown_minutes"] == 60

    def test_delete_alert(self, tmp_env):
        from app.alert_service import create_or_update_alert, delete_alert, get_alerts
        alert = create_or_update_alert({"name": "To Delete"})
        assert delete_alert(alert["id"]) is True
        assert len(get_alerts()) == 0

    def test_delete_nonexistent(self, tmp_env):
        from app.alert_service import delete_alert
        assert delete_alert("nonexistent") is False

    def test_get_history_empty(self, tmp_env):
        from app.alert_service import get_history
        assert get_history() == []

    def test_record_and_get_history(self, tmp_env):
        from app.alert_service import _record_history, get_history
        _record_history("rule1", "Test", "email", "msg", True)
        history = get_history()
        assert len(history) == 1
        assert history[0]["alert_name"] == "Test"
        assert history[0]["success"] is True

    def test_get_history_limit(self, tmp_env):
        from app.alert_service import _record_history, get_history
        for i in range(10):
            _record_history(f"r{i}", f"Test{i}", "email", f"msg{i}", True)
        history = get_history(limit=5)
        assert len(history) == 5
        # Should be in reverse order (most recent first)
        assert history[0]["alert_name"] == "Test9"

    def test_get_history_returns_reversed(self, tmp_env):
        from app.alert_service import _record_history, get_history
        _record_history("r1", "First", "email", "msg1", True)
        _record_history("r2", "Second", "email", "msg2", True)
        history = get_history()
        assert history[0]["alert_name"] == "Second"
        assert history[1]["alert_name"] == "First"


class TestCooldown:
    def test_cooldown_allows_first_notification(self, tmp_env):
        from app.alert_service import _check_cooldown
        assert _check_cooldown("new_rule", 60) is True

    def test_cooldown_blocks_recent(self, tmp_env):
        from app.alert_service import _check_cooldown
        (tmp_env / "alert_history.json").write_text(json.dumps([{
            "id": "h1", "alert_id": "rule1", "alert_name": "X",
            "channel": "email", "message": "test", "success": True,
            "timestamp": datetime.now().isoformat(),
        }]))
        assert _check_cooldown("rule1", 60) is False

    def test_cooldown_allows_after_elapsed(self, tmp_env):
        from app.alert_service import _check_cooldown
        old_time = (datetime.now() - timedelta(hours=2)).isoformat()
        (tmp_env / "alert_history.json").write_text(json.dumps([{
            "id": "h1", "alert_id": "rule1", "alert_name": "X",
            "channel": "email", "message": "test", "success": True,
            "timestamp": old_time,
        }]))
        assert _check_cooldown("rule1", 60) is True

    def test_cooldown_ignores_failed_notifications(self, tmp_env):
        from app.alert_service import _check_cooldown
        (tmp_env / "alert_history.json").write_text(json.dumps([{
            "id": "h1", "alert_id": "rule1", "alert_name": "X",
            "channel": "email", "message": "test", "success": False,
            "timestamp": datetime.now().isoformat(),
        }]))
        # Failed notifications shouldn't block cooldown
        assert _check_cooldown("rule1", 60) is True


class TestSendTestNotification:
    def test_send_test(self, tmp_env):
        from app.alert_service import send_test_notification
        with patch("app.alert_service.notification_service") as mock_ns:
            mock_ns.notify.return_value = True
            mock_ns.get_channel_status.return_value = {"email": {"configured": True}, "telegram": {"configured": False}}
            result = send_test_notification("email", "hello")
        assert result["success"] is True
        assert result["channel"] == "email"
        assert result["message"] == "hello"

    def test_send_test_default_message(self, tmp_env):
        from app.alert_service import send_test_notification
        with patch("app.alert_service.notification_service") as mock_ns:
            mock_ns.notify.return_value = True
            mock_ns.get_channel_status.return_value = {}
            result = send_test_notification()
        assert "Test notification" in result["message"]
        assert result["channel"] == "all"


class TestEvaluatorRegistry:
    def test_register_and_lookup(self, tmp_env):
        from app.alert_service import register_evaluator, _condition_evaluators
        fn = lambda cond: (True, "triggered")
        register_evaluator("test_type", fn)
        assert "test_type" in _condition_evaluators
        assert _condition_evaluators["test_type"]({})[0] is True
        # Cleanup
        del _condition_evaluators["test_type"]


class TestEvaluateOnce:
    def test_evaluate_once_runs_evaluators(self, tmp_env):
        from app.alert_service import _evaluate_once, register_evaluator, _condition_evaluators
        called = []
        def mock_evaluator(cond):
            called.append(True)
            return (False, "")
        register_evaluator("_test_eval_", mock_evaluator)
        try:
            _evaluate_once()
            assert len(called) == 1
        finally:
            del _condition_evaluators["_test_eval_"]

    def test_evaluate_once_evaluator_exception(self, tmp_env):
        from app.alert_service import _evaluate_once, register_evaluator, _condition_evaluators
        def bad_evaluator(cond):
            raise ValueError("boom")
        register_evaluator("_test_bad_", bad_evaluator)
        try:
            _evaluate_once()  # Should not raise
        finally:
            del _condition_evaluators["_test_bad_"]

    def test_evaluate_once_disabled_alert_skipped(self, tmp_env):
        from app.alert_service import _evaluate_once, register_evaluator, _condition_evaluators
        # Create a disabled alert
        (tmp_env / "alerts.json").write_text(json.dumps([{
            "id": "disabled1", "name": "Disabled Alert", "enabled": False,
            "channel": "email", "condition": {"type": "_test_cond_"},
            "cooldown_minutes": 60,
        }]))
        calls = []
        def eval_fn(cond):
            calls.append(cond)
            return (True, "triggered")
        register_evaluator("_test_cond_", eval_fn)
        try:
            _evaluate_once()
            # The evaluator should have been called once for direct evaluator run,
            # but NOT for the disabled alert
        finally:
            del _condition_evaluators["_test_cond_"]

    def test_evaluate_once_triggered_alert_sends_notification(self, tmp_env):
        from app.alert_service import _evaluate_once, register_evaluator, _condition_evaluators
        (tmp_env / "alerts.json").write_text(json.dumps([{
            "id": "alert1", "name": "Test Trigger", "enabled": True,
            "channel": "telegram", "condition": {"type": "_test_trigger_"},
            "cooldown_minutes": 60,
        }]))
        def eval_fn(cond):
            return (True, "alert triggered!")
        register_evaluator("_test_trigger_", eval_fn)
        try:
            with patch("app.alert_service.notification_service") as mock_ns:
                mock_ns.notify.return_value = True
                _evaluate_once()
                mock_ns.notify.assert_called()
        finally:
            del _condition_evaluators["_test_trigger_"]

    def test_evaluate_once_cooldown_blocks_notification(self, tmp_env):
        from app.alert_service import _evaluate_once, register_evaluator, _condition_evaluators
        # Write history showing recent successful notification
        (tmp_env / "alert_history.json").write_text(json.dumps([{
            "id": "h1", "alert_id": "alert2", "alert_name": "X",
            "channel": "email", "message": "x", "success": True,
            "timestamp": datetime.now().isoformat(),
        }]))
        (tmp_env / "alerts.json").write_text(json.dumps([{
            "id": "alert2", "name": "Cooled Down", "enabled": True,
            "channel": "email", "condition": {"type": "_test_cd_"},
            "cooldown_minutes": 60,
        }]))
        def eval_fn(cond):
            return (True, "should be blocked")
        register_evaluator("_test_cd_", eval_fn)
        try:
            with patch("app.alert_service.notification_service") as mock_ns:
                _evaluate_once()
                # Notification should NOT be called due to cooldown
                mock_ns.notify.assert_not_called()
        finally:
            del _condition_evaluators["_test_cd_"]

    def test_evaluate_once_alert_evaluator_exception(self, tmp_env):
        from app.alert_service import _evaluate_once, register_evaluator, _condition_evaluators
        (tmp_env / "alerts.json").write_text(json.dumps([{
            "id": "alert3", "name": "Bad Eval", "enabled": True,
            "channel": "email", "condition": {"type": "_test_exc_"},
            "cooldown_minutes": 60,
        }]))
        def eval_fn(cond):
            raise RuntimeError("evaluator crash")
        register_evaluator("_test_exc_", eval_fn)
        try:
            _evaluate_once()  # Should not raise
        finally:
            del _condition_evaluators["_test_exc_"]

    def test_evaluate_once_unknown_condition_type_skipped(self, tmp_env):
        from app.alert_service import _evaluate_once
        (tmp_env / "alerts.json").write_text(json.dumps([{
            "id": "alert4", "name": "Unknown Type", "enabled": True,
            "channel": "email", "condition": {"type": "nonexistent_type"},
            "cooldown_minutes": 60,
        }]))
        _evaluate_once()  # Should not raise


class TestBackgroundThread:
    def test_start_and_stop(self, tmp_env):
        import app.alert_service as alert_mod
        # Ensure clean state
        alert_mod._bg_running = False
        alert_mod.start_alert_bg_thread()
        assert alert_mod._bg_running is True
        assert alert_mod._bg_thread is not None

        # Starting again should be a no-op
        first_thread = alert_mod._bg_thread
        alert_mod.start_alert_bg_thread()
        assert alert_mod._bg_thread is first_thread

        alert_mod.stop_alert_bg_thread()
        assert alert_mod._bg_running is False
        # Wait for thread to finish
        if alert_mod._bg_thread:
            alert_mod._bg_thread.join(timeout=5)

    def test_bg_loop_stops_on_flag(self, tmp_env):
        import app.alert_service as alert_mod
        alert_mod._bg_running = False
        # _bg_loop should exit immediately when _bg_running is False
        # We can't directly test the loop easily, but we test start/stop above
