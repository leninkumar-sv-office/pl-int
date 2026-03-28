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
    monkeypatch.setattr("app.notification_service._EMAIL_ADDRESS", "sender@gmail.com")
    monkeypatch.setattr("app.notification_service._EMAIL_APP_PASSWORD", "test-pass")
    monkeypatch.setattr("app.notification_service._TELEGRAM_BOT_TOKEN", "")
    monkeypatch.setattr("app.notification_service._TELEGRAM_CHAT_ID", "")
    monkeypatch.setattr(
        "app.notification_service.get_user_dumps_dir",
        lambda uid, email: dumps / email / uid.title(),
    )
    return dumps


@pytest.fixture
def tmp_env_telegram(tmp_path, monkeypatch):
    """Set up temp with telegram configured."""
    dumps = tmp_path / "dumps"
    user_dir = dumps / "test@example.com" / "TestUser" / "settings"
    user_dir.mkdir(parents=True)
    monkeypatch.setattr("app.notification_service._EMAIL_ADDRESS", "sender@gmail.com")
    monkeypatch.setattr("app.notification_service._EMAIL_APP_PASSWORD", "test-pass")
    monkeypatch.setattr("app.notification_service._TELEGRAM_BOT_TOKEN", "bot123:token")
    monkeypatch.setattr("app.notification_service._TELEGRAM_CHAT_ID", "12345")
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

    def test_telegram_configured(self, tmp_env_telegram):
        from app.notification_service import telegram_configured
        assert telegram_configured() is True

    def test_get_channel_status(self, tmp_env):
        from app.notification_service import get_channel_status
        status = get_channel_status()
        assert status["email"]["configured"] is True
        assert status["telegram"]["configured"] is False

    def test_get_channel_status_with_telegram(self, tmp_env_telegram):
        from app.notification_service import get_channel_status
        status = get_channel_status()
        assert status["email"]["configured"] is True
        assert status["telegram"]["configured"] is True
        assert "***" in status["telegram"]["chat_id"]

    def test_email_not_configured(self, tmp_env, monkeypatch):
        from app.notification_service import email_configured, get_channel_status
        monkeypatch.setattr("app.notification_service._EMAIL_ADDRESS", "")
        assert email_configured() is False
        status = get_channel_status()
        assert status["email"]["address"] == ""


class TestUserPrefs:
    def test_save_and_get_prefs(self, tmp_env):
        from app.notification_service import save_user_prefs, get_user_prefs
        saved = save_user_prefs("test@example.com", "testuser", ["a@b.com", "c@d.com"])
        assert saved["emails"] == ["a@b.com", "c@d.com"]
        assert "updated_at" in saved

        prefs = get_user_prefs("test@example.com", "testuser")
        assert prefs["emails"] == ["a@b.com", "c@d.com"]

    def test_dedup_and_normalize(self, tmp_env):
        from app.notification_service import save_user_prefs
        saved = save_user_prefs("test@example.com", "testuser", [
            "A@B.com", "  a@b.com  ", "c@d.com", "A@B.COM",
        ])
        assert saved["emails"] == ["a@b.com", "c@d.com"]

    def test_empty_prefs_for_unknown_user(self, tmp_env):
        from app.notification_service import get_user_prefs
        prefs = get_user_prefs("unknown@x.com", "nobody")
        assert prefs["emails"] == []

    def test_invalid_emails_stripped(self, tmp_env):
        from app.notification_service import save_user_prefs
        saved = save_user_prefs("test@example.com", "testuser", [
            "valid@test.com", "", "  ", "noemail", "also@valid.com",
        ])
        # "noemail" has no @ so it gets filtered
        assert "valid@test.com" in saved["emails"]
        assert "also@valid.com" in saved["emails"]
        assert "" not in saved["emails"]

    def test_get_notification_emails_with_prefs(self, tmp_env):
        from app.notification_service import save_user_prefs, get_user_notification_emails
        save_user_prefs("test@example.com", "testuser", ["notify@test.com"])
        emails = get_user_notification_emails("test@example.com", "testuser")
        assert emails == ["notify@test.com"]

    def test_get_notification_emails_fallback(self, tmp_env):
        from app.notification_service import get_user_notification_emails
        emails = get_user_notification_emails("nobody@x.com", "nobody")
        assert emails == ["sender@gmail.com"]

    def test_get_notification_emails_no_user_id_fallback(self, tmp_env):
        from app.notification_service import get_user_notification_emails
        with patch("app.config.get_users_for_email", return_value=[
            {"id": "testuser", "email": "test@example.com"}
        ]):
            emails = get_user_notification_emails("test@example.com", "")
        # Falls back through all users
        assert isinstance(emails, list)

    def test_get_notification_emails_no_user_id_no_users(self, tmp_env):
        from app.notification_service import get_user_notification_emails
        with patch("app.config.get_users_for_email", return_value=[]):
            emails = get_user_notification_emails("test@example.com", "")
        assert emails == ["sender@gmail.com"]

    def test_get_notification_emails_no_email_address(self, tmp_env, monkeypatch):
        from app.notification_service import get_user_notification_emails
        monkeypatch.setattr("app.notification_service._EMAIL_ADDRESS", "")
        emails = get_user_notification_emails("nobody@x.com", "nobody")
        assert emails == []


class TestSendEmail:
    def test_send_email_success(self, tmp_env):
        from app.notification_service import send_email
        with patch("app.notification_service.smtplib.SMTP") as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value.__enter__ = MagicMock(return_value=mock_server)
            mock_smtp.return_value.__exit__ = MagicMock(return_value=False)
            result = send_email("Test", "Body")
        assert result is True

    def test_send_email_with_html(self, tmp_env):
        from app.notification_service import send_email
        with patch("app.notification_service.smtplib.SMTP") as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value.__enter__ = MagicMock(return_value=mock_server)
            mock_smtp.return_value.__exit__ = MagicMock(return_value=False)
            result = send_email("Test", "Body", html_body="<h1>HTML Body</h1>")
        assert result is True

    def test_send_email_custom_recipients(self, tmp_env):
        from app.notification_service import send_email
        with patch("app.notification_service.smtplib.SMTP") as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value.__enter__ = MagicMock(return_value=mock_server)
            mock_smtp.return_value.__exit__ = MagicMock(return_value=False)
            result = send_email("Test", "Body", recipients=["a@b.com", "c@d.com"])
        assert result is True

    def test_send_email_not_configured(self, tmp_env, monkeypatch):
        from app.notification_service import send_email
        monkeypatch.setattr("app.notification_service._EMAIL_APP_PASSWORD", "")
        result = send_email("Test", "Body")
        assert result is False

    def test_send_email_empty_recipients(self, tmp_env):
        from app.notification_service import send_email
        result = send_email("Test", "Body", recipients=[])
        assert result is False

    def test_send_email_exception(self, tmp_env):
        from app.notification_service import send_email
        with patch("app.notification_service.smtplib.SMTP", side_effect=Exception("SMTP error")):
            result = send_email("Test", "Body")
        assert result is False


class TestSendTelegram:
    def test_send_telegram_not_configured(self, tmp_env):
        from app.notification_service import send_telegram
        result = send_telegram("test message")
        assert result is False

    def test_send_telegram_success(self, tmp_env_telegram):
        from app.notification_service import send_telegram
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        with patch("app.notification_service.requests.post", return_value=mock_resp):
            result = send_telegram("test message")
        assert result is True

    def test_send_telegram_api_error(self, tmp_env_telegram):
        from app.notification_service import send_telegram
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.text = "Bad Request"
        with patch("app.notification_service.requests.post", return_value=mock_resp):
            result = send_telegram("test message")
        assert result is False

    def test_send_telegram_exception(self, tmp_env_telegram):
        from app.notification_service import send_telegram
        with patch("app.notification_service.requests.post", side_effect=Exception("Network error")):
            result = send_telegram("test message")
        assert result is False


class TestNotify:
    def test_notify_email_only(self, tmp_env):
        from app.notification_service import notify
        with patch("app.notification_service.send_email", return_value=True) as mock:
            result = notify("email", "Subject", "Body")
        assert result is True
        mock.assert_called_once()

    def test_notify_telegram_only(self, tmp_env):
        from app.notification_service import notify
        with patch("app.notification_service.send_telegram", return_value=True) as mock:
            result = notify("telegram", "Subject", "Body")
        assert result is True
        mock.assert_called_once()

    def test_notify_all_channels(self, tmp_env):
        from app.notification_service import notify
        with patch("app.notification_service.send_email", return_value=True), \
             patch("app.notification_service.send_telegram", return_value=False):
            result = notify("all", "Subject", "Body")
        assert result is True

    def test_notify_with_html(self, tmp_env):
        from app.notification_service import notify
        with patch("app.notification_service.send_email", return_value=True) as mock_email:
            result = notify("email", "Subject", "Body", html_body="<h1>HTML</h1>")
        assert result is True

    def test_notify_with_user_email(self, tmp_env):
        from app.notification_service import notify
        with patch("app.notification_service.send_email", return_value=True) as mock_email, \
             patch("app.notification_service.get_user_notification_emails", return_value=["user@x.com"]):
            result = notify("email", "Subject", "Body", user_email="user@x.com")
        assert result is True

    def test_notify_unknown_channel(self, tmp_env):
        from app.notification_service import notify
        result = notify("unknown_channel", "Subject", "Body")
        assert result is False
