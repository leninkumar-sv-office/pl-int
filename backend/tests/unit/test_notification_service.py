"""Tests for notification_service module."""
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


@pytest.fixture
def tmp_env(tmp_path, monkeypatch):
    """Set up temp dumps dir and mock env vars."""
    dumps = tmp_path / "dumps"
    user_dir = dumps / "test@example.com" / "TestUser" / "settings"
    user_dir.mkdir(parents=True)
    monkeypatch.setattr("app.notification_service.DUMPS_BASE", dumps)
    monkeypatch.setattr("app.notification_service._EMAIL_ADDRESS", "sender@gmail.com")
    monkeypatch.setattr("app.notification_service._EMAIL_APP_PASSWORD", "test-pass")
    monkeypatch.setattr("app.notification_service._TELEGRAM_BOT_TOKEN", "")
    monkeypatch.setattr("app.notification_service._TELEGRAM_CHAT_ID", "")
    # Mock get_user_dumps_dir to return our temp path
    monkeypatch.setattr(
        "app.notification_service.get_user_dumps_dir",
        lambda uid, email: dumps / email / uid.title(),
    )
    return dumps


class TestChannelStatus:
    def test_email_configured(self, tmp_env):
        from app.notification_service import email_configured
        assert email_configured() is True

    def test_telegram_not_configured(self, tmp_env):
        from app.notification_service import telegram_configured
        assert telegram_configured() is False

    def test_get_channel_status(self, tmp_env):
        from app.notification_service import get_channel_status
        status = get_channel_status()
        assert status["email"]["configured"] is True
        assert status["telegram"]["configured"] is False


class TestUserPrefs:
    def test_save_and_get_prefs(self, tmp_env):
        from app.notification_service import save_user_prefs, get_user_prefs
        with patch("app.notification_service._sync_prefs_to_drive"):
            saved = save_user_prefs("test@example.com", "testuser", ["a@b.com", "c@d.com"])
        assert saved["emails"] == ["a@b.com", "c@d.com"]
        assert "updated_at" in saved

        prefs = get_user_prefs("test@example.com", "testuser")
        assert prefs["emails"] == ["a@b.com", "c@d.com"]

    def test_dedup_and_normalize(self, tmp_env):
        from app.notification_service import save_user_prefs
        with patch("app.notification_service._sync_prefs_to_drive"):
            saved = save_user_prefs("test@example.com", "testuser", [
                "A@B.com", "  a@b.com  ", "c@d.com", "A@B.COM",
            ])
        assert saved["emails"] == ["a@b.com", "c@d.com"]

    def test_empty_prefs_for_unknown_user(self, tmp_env):
        from app.notification_service import get_user_prefs
        prefs = get_user_prefs("unknown@x.com", "nobody")
        assert prefs["emails"] == []

    def test_get_notification_emails_with_prefs(self, tmp_env):
        from app.notification_service import save_user_prefs, get_user_notification_emails
        with patch("app.notification_service._sync_prefs_to_drive"):
            save_user_prefs("test@example.com", "testuser", ["notify@test.com"])
        emails = get_user_notification_emails("test@example.com", "testuser")
        assert emails == ["notify@test.com"]

    def test_get_notification_emails_fallback(self, tmp_env):
        from app.notification_service import get_user_notification_emails
        emails = get_user_notification_emails("nobody@x.com", "nobody")
        assert emails == ["sender@gmail.com"]  # falls back to SMTP sender


class TestSendEmail:
    def test_send_email_success(self, tmp_env):
        from app.notification_service import send_email
        with patch("app.notification_service.smtplib.SMTP") as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value.__enter__ = MagicMock(return_value=mock_server)
            mock_smtp.return_value.__exit__ = MagicMock(return_value=False)
            result = send_email("Test", "Body")
        assert result is True

    def test_send_email_not_configured(self, tmp_env, monkeypatch):
        from app.notification_service import send_email
        monkeypatch.setattr("app.notification_service._EMAIL_APP_PASSWORD", "")
        result = send_email("Test", "Body")
        assert result is False

    def test_send_telegram_not_configured(self, tmp_env):
        from app.notification_service import send_telegram
        result = send_telegram("test message")
        assert result is False


class TestNotify:
    def test_notify_email_only(self, tmp_env):
        from app.notification_service import notify
        with patch("app.notification_service.send_email", return_value=True) as mock:
            result = notify("email", "Subject", "Body")
        assert result is True
        mock.assert_called_once()

    def test_notify_all_channels(self, tmp_env):
        from app.notification_service import notify
        with patch("app.notification_service.send_email", return_value=True), \
             patch("app.notification_service.send_telegram", return_value=False):
            result = notify("all", "Subject", "Body")
        assert result is True  # at least one succeeded
