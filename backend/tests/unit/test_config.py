"""Tests for app/config.py — user management and dumps directory resolution."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest


# ===================================================================
# get_users
# ===================================================================


class TestGetUsers:
    """Tests for get_users()."""

    def test_reads_from_users_json(self, tmp_data_dir):
        import app.config as config

        users_file = tmp_data_dir / "users.json"
        expected = [
            {"id": "testuser", "name": "TestUser", "avatar": "T", "color": "#4e7cff", "email": "test@example.com"}
        ]

        with patch.object(config, "_USERS_FILE", users_file):
            result = config.get_users()

        assert result == expected

    def test_returns_defaults_when_file_missing(self, tmp_path):
        import app.config as config

        missing_file = tmp_path / "data" / "users.json"
        # Ensure parent exists so save_users can write to it
        missing_file.parent.mkdir(parents=True, exist_ok=True)

        with patch.object(config, "_USERS_FILE", missing_file), \
             patch("app.config.save_users") as mock_save:
            # save_users is called to bootstrap — mock it to avoid drive_service import
            result = config.get_users()

        assert result == config._DEFAULT_USERS
        mock_save.assert_called_once_with(config._DEFAULT_USERS)

    def test_returns_defaults_on_invalid_json(self, tmp_path):
        import app.config as config

        bad_file = tmp_path / "users.json"
        bad_file.write_text("not-valid-json!!!")

        with patch.object(config, "_USERS_FILE", bad_file), \
             patch("app.config.save_users"):
            result = config.get_users()

        assert result == config._DEFAULT_USERS

    def test_empty_list_in_file(self, tmp_path):
        import app.config as config

        users_file = tmp_path / "users.json"
        users_file.write_text(json.dumps([]))

        with patch.object(config, "_USERS_FILE", users_file):
            result = config.get_users()

        assert result == []

    def test_multiple_users(self, tmp_path):
        import app.config as config

        users = [
            {"id": "alice", "name": "Alice", "avatar": "A", "color": "#ff0000", "email": "alice@example.com"},
            {"id": "bob", "name": "Bob", "avatar": "B", "color": "#00ff00", "email": "bob@example.com"},
        ]
        users_file = tmp_path / "users.json"
        users_file.write_text(json.dumps(users))

        with patch.object(config, "_USERS_FILE", users_file):
            result = config.get_users()

        assert len(result) == 2
        assert result[0]["id"] == "alice"
        assert result[1]["id"] == "bob"


# ===================================================================
# save_users
# ===================================================================


class TestSaveUsers:
    """Tests for save_users()."""

    def test_writes_to_users_json(self, tmp_path):
        import app.config as config

        users_file = tmp_path / "data" / "users.json"
        users = [{"id": "alice", "name": "Alice", "avatar": "A", "color": "#ff0000"}]

        with patch.object(config, "_USERS_FILE", users_file), \
             patch("app.drive_service.sync_data_file", return_value=None):
            config.save_users(users)

        assert users_file.exists()
        stored = json.loads(users_file.read_text())
        assert stored == users

    def test_creates_parent_directories(self, tmp_path):
        import app.config as config

        users_file = tmp_path / "nested" / "dir" / "users.json"

        with patch.object(config, "_USERS_FILE", users_file), \
             patch("app.drive_service.sync_data_file", return_value=None):
            config.save_users([{"id": "x"}])

        assert users_file.exists()

    def test_overwrites_existing_file(self, tmp_path):
        import app.config as config

        users_file = tmp_path / "users.json"
        users_file.write_text(json.dumps([{"id": "old"}]))

        new_users = [{"id": "new"}]
        with patch.object(config, "_USERS_FILE", users_file), \
             patch("app.drive_service.sync_data_file", return_value=None):
            config.save_users(new_users)

        stored = json.loads(users_file.read_text())
        assert stored == new_users

    def test_drive_sync_failure_does_not_raise(self, tmp_path):
        """save_users catches drive_service import/call failures silently."""
        import app.config as config

        users_file = tmp_path / "users.json"
        with patch.object(config, "_USERS_FILE", users_file), \
             patch("app.drive_service.sync_data_file", side_effect=Exception("network fail")):
            # Should not raise
            config.save_users([{"id": "x"}])

        assert users_file.exists()


# ===================================================================
# get_user_by_id
# ===================================================================


class TestGetUserById:
    """Tests for get_user_by_id()."""

    def test_finds_existing_user(self, tmp_data_dir):
        import app.config as config

        with patch.object(config, "_USERS_FILE", tmp_data_dir / "users.json"):
            result = config.get_user_by_id("testuser")

        assert result is not None
        assert result["id"] == "testuser"
        assert result["name"] == "TestUser"

    def test_returns_none_for_unknown_id(self, tmp_data_dir):
        import app.config as config

        with patch.object(config, "_USERS_FILE", tmp_data_dir / "users.json"):
            result = config.get_user_by_id("nonexistent")

        assert result is None


# ===================================================================
# get_user_email
# ===================================================================


class TestGetUserEmail:
    """Tests for get_user_email()."""

    def test_returns_email_for_known_user(self, tmp_data_dir):
        import app.config as config

        with patch.object(config, "_USERS_FILE", tmp_data_dir / "users.json"):
            result = config.get_user_email("testuser")

        assert result == "test@example.com"

    def test_returns_none_for_unknown_user(self, tmp_data_dir):
        import app.config as config

        with patch.object(config, "_USERS_FILE", tmp_data_dir / "users.json"):
            result = config.get_user_email("nonexistent")

        assert result is None

    def test_returns_none_when_user_has_no_email_field(self, tmp_path):
        import app.config as config

        users_file = tmp_path / "users.json"
        users_file.write_text(json.dumps([{"id": "noemail", "name": "NoEmail"}]))

        with patch.object(config, "_USERS_FILE", users_file):
            result = config.get_user_email("noemail")

        assert result is None


# ===================================================================
# get_users_for_email
# ===================================================================


class TestGetUsersForEmail:
    """Tests for get_users_for_email()."""

    def test_filters_by_email(self, tmp_data_dir):
        import app.config as config

        with patch.object(config, "_USERS_FILE", tmp_data_dir / "users.json"):
            result = config.get_users_for_email("test@example.com")

        assert len(result) == 1
        assert result[0]["id"] == "testuser"

    def test_case_insensitive_match(self, tmp_data_dir):
        import app.config as config

        with patch.object(config, "_USERS_FILE", tmp_data_dir / "users.json"):
            result = config.get_users_for_email("TEST@EXAMPLE.COM")

        assert len(result) == 1

    def test_returns_empty_list_for_unknown_email(self, tmp_data_dir):
        import app.config as config

        with patch.object(config, "_USERS_FILE", tmp_data_dir / "users.json"):
            result = config.get_users_for_email("unknown@example.com")

        assert result == []

    def test_multiple_users_same_email(self, tmp_path):
        import app.config as config

        users = [
            {"id": "alice", "name": "Alice", "email": "shared@example.com"},
            {"id": "bob", "name": "Bob", "email": "shared@example.com"},
            {"id": "carol", "name": "Carol", "email": "other@example.com"},
        ]
        users_file = tmp_path / "users.json"
        users_file.write_text(json.dumps(users))

        with patch.object(config, "_USERS_FILE", users_file):
            result = config.get_users_for_email("shared@example.com")

        assert len(result) == 2
        ids = [u["id"] for u in result]
        assert "alice" in ids
        assert "bob" in ids

    def test_users_without_email_field_skipped(self, tmp_path):
        import app.config as config

        users = [
            {"id": "noemail", "name": "NoEmail"},
            {"id": "hasemail", "name": "HasEmail", "email": "test@example.com"},
        ]
        users_file = tmp_path / "users.json"
        users_file.write_text(json.dumps(users))

        with patch.object(config, "_USERS_FILE", users_file):
            result = config.get_users_for_email("test@example.com")

        assert len(result) == 1
        assert result[0]["id"] == "hasemail"


# ===================================================================
# get_user_dumps_dir
# ===================================================================


class TestGetUserDumpsDir:
    """Tests for get_user_dumps_dir()."""

    def test_returns_email_scoped_path(self, tmp_data_dir, tmp_dumps_dir):
        import app.config as config

        with patch.object(config, "_USERS_FILE", tmp_data_dir / "users.json"), \
             patch.object(config, "DUMPS_BASE", tmp_dumps_dir):
            result = config.get_user_dumps_dir("testuser", "test@example.com")

        expected = tmp_dumps_dir / "test@example.com" / "TestUser"
        assert result == expected
        assert result.is_dir()

    def test_creates_asset_subdirectories(self, tmp_data_dir, tmp_dumps_dir):
        import app.config as config

        with patch.object(config, "_USERS_FILE", tmp_data_dir / "users.json"), \
             patch.object(config, "DUMPS_BASE", tmp_dumps_dir):
            result = config.get_user_dumps_dir("testuser", "test@example.com")

        for sub in ["Stocks", "Mutual Funds", "FD", "RD", "PPF", "NPS", "Standing Instructions"]:
            assert (result / sub).is_dir(), f"Missing subdir: {sub}"

    def test_legacy_fallback_no_email(self, tmp_path):
        import app.config as config

        users = [{"id": "legacy", "name": "LegacyUser", "avatar": "L", "color": "#000"}]
        users_file = tmp_path / "users.json"
        users_file.write_text(json.dumps(users))
        dumps = tmp_path / "dumps"

        with patch.object(config, "_USERS_FILE", users_file), \
             patch.object(config, "DUMPS_BASE", dumps):
            result = config.get_user_dumps_dir("legacy")

        expected = dumps / "LegacyUser"
        assert result == expected
        assert result.is_dir()

    def test_unknown_user_uses_id_as_folder_name(self, tmp_path):
        import app.config as config

        users_file = tmp_path / "users.json"
        users_file.write_text(json.dumps([]))
        dumps = tmp_path / "dumps"

        with patch.object(config, "_USERS_FILE", users_file), \
             patch.object(config, "DUMPS_BASE", dumps):
            result = config.get_user_dumps_dir("mystery_id", "x@example.com")

        expected = dumps / "x@example.com" / "mystery_id"
        assert result == expected

    def test_user_email_from_record_when_not_passed(self, tmp_data_dir, tmp_dumps_dir):
        """When email is not passed, it should be resolved from user record."""
        import app.config as config

        with patch.object(config, "_USERS_FILE", tmp_data_dir / "users.json"), \
             patch.object(config, "DUMPS_BASE", tmp_dumps_dir):
            result = config.get_user_dumps_dir("testuser")

        # testuser has email "test@example.com" in the fixture
        expected = tmp_dumps_dir / "test@example.com" / "TestUser"
        assert result == expected
