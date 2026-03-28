"""Tests for user_settings module."""
import json
from unittest.mock import patch

import pytest


@pytest.fixture
def tmp_env(tmp_path, monkeypatch):
    dumps = tmp_path / "dumps"
    (dumps / "test@example.com" / "TestUser" / "settings").mkdir(parents=True)
    monkeypatch.setattr(
        "app.user_settings.get_user_dumps_dir",
        lambda uid, email: dumps / email / uid.title(),
    )
    return dumps


class TestUserSettings:
    def test_get_defaults(self, tmp_env):
        from app.user_settings import get_settings
        s = get_settings("testuser", "test@example.com")
        assert s["page_refresh_interval"] == 600

    def test_save_and_get(self, tmp_env):
        from app.user_settings import save_settings, get_settings
        saved = save_settings("testuser", "test@example.com", {"page_refresh_interval": 300})
        assert saved["page_refresh_interval"] == 300
        assert "updated_at" in saved

        loaded = get_settings("testuser", "test@example.com")
        assert loaded["page_refresh_interval"] == 300

    def test_merge_preserves_existing(self, tmp_env):
        from app.user_settings import save_settings, get_settings
        save_settings("testuser", "test@example.com", {"page_refresh_interval": 120})
        save_settings("testuser", "test@example.com", {"custom_key": "hello"})

        loaded = get_settings("testuser", "test@example.com")
        assert loaded["page_refresh_interval"] == 120
        assert loaded["custom_key"] == "hello"

    def test_per_user_isolation(self, tmp_env):
        from app.user_settings import save_settings, get_settings
        (tmp_env / "test@example.com" / "Appa" / "settings").mkdir(parents=True)
        save_settings("testuser", "test@example.com", {"page_refresh_interval": 100})
        save_settings("appa", "test@example.com", {"page_refresh_interval": 200})

        assert get_settings("testuser", "test@example.com")["page_refresh_interval"] == 100
        assert get_settings("appa", "test@example.com")["page_refresh_interval"] == 200
