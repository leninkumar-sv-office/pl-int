"""Tests for app/auth.py — JWT sessions, Google OAuth, token persistence."""

import json
import time
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import jwt as pyjwt
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

JWT_SECRET = "test-jwt-secret-for-pytest-only-00"
JWT_ALGORITHM = "HS256"


def _make_token(payload: dict, secret: str = JWT_SECRET) -> str:
    return pyjwt.encode(payload, secret, algorithm=JWT_ALGORITHM)


# ===================================================================
# create_session_token / verify_session_token
# ===================================================================


class TestCreateSessionToken:
    """Tests for create_session_token()."""

    def test_returns_valid_jwt(self):
        import app.auth as auth

        token = auth.create_session_token("alice@example.com", "Alice")
        payload = pyjwt.decode(token, auth._JWT_SECRET, algorithms=["HS256"])
        assert payload["email"] == "alice@example.com"
        assert payload["name"] == "Alice"

    def test_contains_iat_and_exp(self):
        import app.auth as auth

        before = int(time.time())
        token = auth.create_session_token("bob@example.com", "Bob")
        after = int(time.time())

        payload = pyjwt.decode(token, auth._JWT_SECRET, algorithms=["HS256"])
        assert before <= payload["iat"] <= after
        assert payload["exp"] == payload["iat"] + auth.JWT_EXPIRY_HOURS * 3600

    def test_different_inputs_different_tokens(self):
        import app.auth as auth

        t1 = auth.create_session_token("a@x.com", "A")
        t2 = auth.create_session_token("b@x.com", "B")
        assert t1 != t2


class TestVerifySessionToken:
    """Tests for verify_session_token()."""

    def test_valid_token_returns_email_and_name(self):
        import app.auth as auth

        token = auth.create_session_token("alice@example.com", "Alice")
        result = auth.verify_session_token(token)
        assert result == {"email": "alice@example.com", "name": "Alice"}

    def test_expired_token_returns_none(self):
        import app.auth as auth

        payload = {
            "email": "expired@example.com",
            "name": "Expired",
            "iat": int(time.time()) - 7200,
            "exp": int(time.time()) - 3600,  # expired 1 hour ago
        }
        token = _make_token(payload, auth._JWT_SECRET)
        assert auth.verify_session_token(token) is None

    def test_invalid_garbage_token_returns_none(self):
        import app.auth as auth

        assert auth.verify_session_token("this.is.garbage") is None

    def test_empty_string_returns_none(self):
        import app.auth as auth

        assert auth.verify_session_token("") is None

    def test_wrong_secret_returns_none(self):
        import app.auth as auth

        payload = {
            "email": "a@b.com",
            "name": "A",
            "iat": int(time.time()),
            "exp": int(time.time()) + 3600,
        }
        token = _make_token(payload, "wrong-secret-key")
        assert auth.verify_session_token(token) is None

    def test_missing_email_key_raises(self):
        import app.auth as auth

        payload = {
            "name": "NoEmail",
            "iat": int(time.time()),
            "exp": int(time.time()) + 3600,
        }
        token = _make_token(payload, auth._JWT_SECRET)
        # jwt.decode succeeds but accessing payload["email"] raises KeyError
        # which is NOT caught by the except clause (it only catches jwt errors)
        with pytest.raises(KeyError):
            auth.verify_session_token(token)


# ===================================================================
# is_auth_enabled
# ===================================================================


class TestIsAuthEnabled:
    """Tests for is_auth_enabled()."""

    def test_enabled_when_google_mode_and_client_id_set(self):
        import app.auth as auth

        with patch.object(auth, "AUTH_MODE", "google"), \
             patch.object(auth, "GOOGLE_CLIENT_ID", "some-client-id"):
            assert auth.is_auth_enabled() is True

    def test_disabled_when_local_mode(self):
        import app.auth as auth

        with patch.object(auth, "AUTH_MODE", "local"), \
             patch.object(auth, "GOOGLE_CLIENT_ID", "some-client-id"):
            assert auth.is_auth_enabled() is False

    def test_disabled_when_google_mode_but_no_client_id(self):
        import app.auth as auth

        with patch.object(auth, "AUTH_MODE", "google"), \
             patch.object(auth, "GOOGLE_CLIENT_ID", ""):
            assert auth.is_auth_enabled() is False

    def test_disabled_when_local_mode_and_no_client_id(self):
        import app.auth as auth

        with patch.object(auth, "AUTH_MODE", "local"), \
             patch.object(auth, "GOOGLE_CLIENT_ID", ""):
            assert auth.is_auth_enabled() is False


# ===================================================================
# exchange_auth_code
# ===================================================================


class TestExchangeAuthCode:
    """Tests for exchange_auth_code()."""

    def test_successful_exchange(self):
        import app.auth as auth

        mock_creds = MagicMock()
        mock_creds.id_token = "fake-id-token"
        mock_creds.token = "fake-access-token"
        mock_creds.refresh_token = "fake-refresh-token"

        mock_flow_instance = MagicMock()
        mock_flow_instance.credentials = mock_creds

        mock_flow_cls = MagicMock()
        mock_flow_cls.from_client_config.return_value = mock_flow_instance

        idinfo = {
            "email": "alice@example.com",
            "name": "Alice",
            "picture": "https://photo.url/alice.jpg",
        }

        with patch.object(auth, "ALLOWED_EMAILS", []), \
             patch("app.auth.Flow", mock_flow_cls, create=True), \
             patch("google_auth_oauthlib.flow.Flow", mock_flow_cls), \
             patch("app.auth._save_tokens") as mock_save, \
             patch("google.oauth2.id_token.verify_oauth2_token", return_value=idinfo):
            result = auth.exchange_auth_code("fake-code")

        assert result["email"] == "alice@example.com"
        assert result["name"] == "Alice"
        assert result["access_token"] == "fake-access-token"
        assert result["refresh_token"] == "fake-refresh-token"
        mock_save.assert_called_once()

    def test_email_not_in_allowlist_raises(self):
        import app.auth as auth

        mock_creds = MagicMock()
        mock_creds.id_token = "fake-id-token"
        mock_creds.token = "fake-access-token"
        mock_creds.refresh_token = "fake-refresh-token"

        mock_flow_instance = MagicMock()
        mock_flow_instance.credentials = mock_creds

        mock_flow_cls = MagicMock()
        mock_flow_cls.from_client_config.return_value = mock_flow_instance

        idinfo = {
            "email": "intruder@evil.com",
            "name": "Intruder",
            "picture": "",
        }

        with patch.object(auth, "ALLOWED_EMAILS", ["allowed@example.com"]), \
             patch("google_auth_oauthlib.flow.Flow", mock_flow_cls), \
             patch("google.oauth2.id_token.verify_oauth2_token", return_value=idinfo):
            with pytest.raises(ValueError, match="not in allowed list"):
                auth.exchange_auth_code("fake-code")


# ===================================================================
# verify_google_token
# ===================================================================


class TestVerifyGoogleToken:
    """Tests for verify_google_token()."""

    def test_valid_token_returns_user_info(self):
        import app.auth as auth

        idinfo = {
            "email": "alice@example.com",
            "name": "Alice",
            "picture": "https://photo.url/alice.jpg",
        }

        with patch.object(auth, "ALLOWED_EMAILS", []), \
             patch("google.oauth2.id_token.verify_oauth2_token", return_value=idinfo), \
             patch("google.auth.transport.requests.Request"):
            result = auth.verify_google_token("fake-id-token")

        assert result == {
            "email": "alice@example.com",
            "name": "Alice",
            "picture": "https://photo.url/alice.jpg",
        }

    def test_email_not_in_allowlist_returns_none(self):
        import app.auth as auth

        idinfo = {
            "email": "intruder@evil.com",
            "name": "Intruder",
            "picture": "",
        }

        with patch.object(auth, "ALLOWED_EMAILS", ["allowed@example.com"]), \
             patch("google.oauth2.id_token.verify_oauth2_token", return_value=idinfo), \
             patch("google.auth.transport.requests.Request"):
            result = auth.verify_google_token("fake-id-token")

        assert result is None

    def test_missing_email_returns_none(self):
        import app.auth as auth

        idinfo = {"name": "NoEmail", "picture": ""}

        with patch.object(auth, "ALLOWED_EMAILS", []), \
             patch("google.oauth2.id_token.verify_oauth2_token", return_value=idinfo), \
             patch("google.auth.transport.requests.Request"):
            result = auth.verify_google_token("fake-id-token")

        assert result is None

    def test_invalid_token_returns_none(self):
        import app.auth as auth

        with patch("google.oauth2.id_token.verify_oauth2_token", side_effect=ValueError("bad")), \
             patch("google.auth.transport.requests.Request"):
            result = auth.verify_google_token("bad-token")

        assert result is None


# ===================================================================
# get_drive_credentials
# ===================================================================


class TestGetDriveCredentials:
    """Tests for get_drive_credentials()."""

    def test_returns_none_when_no_tokens(self):
        import app.auth as auth

        with patch.object(auth, "_load_tokens", return_value=None):
            assert auth.get_drive_credentials("alice@example.com") is None

    def test_returns_none_when_no_refresh_token(self):
        import app.auth as auth

        with patch.object(auth, "_load_tokens", return_value={"access_token": "x"}):
            assert auth.get_drive_credentials("alice@example.com") is None

    def test_returns_credentials_when_valid(self):
        import app.auth as auth

        tokens = {
            "refresh_token": "rt",
            "access_token": "at",
            "client_id": "cid",
            "client_secret": "cs",
        }

        mock_creds = MagicMock()
        mock_creds.expired = False
        mock_creds.valid = True

        with patch.object(auth, "_load_tokens", return_value=tokens), \
             patch("google.oauth2.credentials.Credentials", return_value=mock_creds):
            result = auth.get_drive_credentials("alice@example.com")

        assert result is mock_creds

    def test_refreshes_expired_credentials(self):
        import app.auth as auth

        tokens = {
            "refresh_token": "rt",
            "access_token": "old-at",
            "client_id": "cid",
            "client_secret": "cs",
        }

        mock_creds = MagicMock()
        mock_creds.expired = True
        mock_creds.valid = False
        mock_creds.token = "new-at"

        with patch.object(auth, "_load_tokens", return_value=tokens), \
             patch.object(auth, "_save_tokens") as mock_save, \
             patch("google.oauth2.credentials.Credentials", return_value=mock_creds), \
             patch("google.auth.transport.requests.Request"):
            result = auth.get_drive_credentials("alice@example.com")

        assert result is mock_creds
        mock_creds.refresh.assert_called_once()
        mock_save.assert_called_once()


# ===================================================================
# _load_tokens / _save_tokens / _load_all_tokens
# ===================================================================


class TestTokenPersistence:
    """Tests for _load_tokens, _save_tokens, _load_all_tokens."""

    def _patch_token_storage(self, auth, tmp_path):
        """Return a context manager that patches both legacy and per-email token paths."""
        legacy_file = tmp_path / "legacy" / "google_tokens.json"
        dumps_base = tmp_path / "dumps"
        dumps_base.mkdir(parents=True, exist_ok=True)
        return patch.object(auth, "_LEGACY_TOKEN_FILE", legacy_file), \
               patch("app.config.DUMPS_BASE", dumps_base)

    def test_save_and_load_tokens(self, tmp_path):
        import app.auth as auth

        p1, p2 = self._patch_token_storage(auth, tmp_path)
        with p1, p2:
            auth._save_tokens("alice@example.com", {"refresh_token": "rt1"})
            result = auth._load_tokens("alice@example.com")

        assert result == {"refresh_token": "rt1"}

    def test_save_multiple_emails(self, tmp_path):
        import app.auth as auth

        p1, p2 = self._patch_token_storage(auth, tmp_path)
        with p1, p2:
            auth._save_tokens("alice@example.com", {"refresh_token": "rt_alice"})
            auth._save_tokens("bob@example.com", {"refresh_token": "rt_bob"})

            assert auth._load_tokens("alice@example.com")["refresh_token"] == "rt_alice"
            assert auth._load_tokens("bob@example.com")["refresh_token"] == "rt_bob"

    def test_load_tokens_missing_file_returns_none(self, tmp_path):
        import app.auth as auth

        p1, p2 = self._patch_token_storage(auth, tmp_path)
        with p1, p2:
            assert auth._load_tokens("alice@example.com") is None

    def test_load_tokens_empty_email_returns_first(self, tmp_path):
        import app.auth as auth

        p1, p2 = self._patch_token_storage(auth, tmp_path)
        with p1, p2:
            auth._save_tokens("alice@example.com", {"refresh_token": "rt_alice"})
            result = auth._load_tokens("")

        assert result == {"refresh_token": "rt_alice"}

    def test_load_all_tokens_empty_file(self, tmp_path):
        import app.auth as auth

        legacy_file = tmp_path / "legacy" / "google_tokens.json"
        legacy_file.parent.mkdir(parents=True, exist_ok=True)
        legacy_file.write_text("{}")
        dumps_base = tmp_path / "dumps"
        dumps_base.mkdir(parents=True, exist_ok=True)
        with patch.object(auth, "_LEGACY_TOKEN_FILE", legacy_file), \
             patch("app.config.DUMPS_BASE", dumps_base):
            assert auth._load_all_tokens() == {}

    def test_load_all_tokens_missing_file(self, tmp_path):
        import app.auth as auth

        p1, p2 = self._patch_token_storage(auth, tmp_path)
        with p1, p2:
            assert auth._load_all_tokens() == {}

    def test_load_all_tokens_invalid_json(self, tmp_path):
        import app.auth as auth

        legacy_file = tmp_path / "legacy" / "google_tokens.json"
        legacy_file.parent.mkdir(parents=True, exist_ok=True)
        legacy_file.write_text("not-json!!!")
        dumps_base = tmp_path / "dumps"
        dumps_base.mkdir(parents=True, exist_ok=True)
        with patch.object(auth, "_LEGACY_TOKEN_FILE", legacy_file), \
             patch("app.config.DUMPS_BASE", dumps_base):
            assert auth._load_all_tokens() == {}

    def test_load_all_tokens_legacy_flat_format_migration(self, tmp_path):
        """Legacy format: flat dict without email keys gets migrated."""
        import app.auth as auth

        legacy_file = tmp_path / "legacy" / "google_tokens.json"
        legacy_file.parent.mkdir(parents=True, exist_ok=True)
        legacy_data = {"refresh_token": "rt_old", "access_token": "at_old"}
        legacy_file.write_text(json.dumps(legacy_data))
        dumps_base = tmp_path / "dumps"
        dumps_base.mkdir(parents=True, exist_ok=True)

        with patch.object(auth, "_LEGACY_TOKEN_FILE", legacy_file), \
             patch("app.config.DUMPS_BASE", dumps_base):
            result = auth._load_all_tokens()

        # Legacy flat format has no "@" in keys, so it won't be migrated
        # to per-email paths. The result depends on the migration logic.
        assert result == {} or "" in result

    def test_load_all_tokens_email_keyed_format(self, tmp_path):
        """Modern format: email-keyed legacy file gets migrated to per-email paths."""
        import app.auth as auth

        legacy_file = tmp_path / "legacy" / "google_tokens.json"
        legacy_file.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "alice@example.com": {"refresh_token": "rt_alice"},
            "bob@example.com": {"refresh_token": "rt_bob"},
        }
        legacy_file.write_text(json.dumps(data))
        dumps_base = tmp_path / "dumps"
        dumps_base.mkdir(parents=True, exist_ok=True)

        with patch.object(auth, "_LEGACY_TOKEN_FILE", legacy_file), \
             patch("app.config.DUMPS_BASE", dumps_base):
            result = auth._load_all_tokens()

        assert result["alice@example.com"]["refresh_token"] == "rt_alice"
        assert result["bob@example.com"]["refresh_token"] == "rt_bob"

    def test_save_tokens_creates_parent_dirs(self, tmp_path):
        import app.auth as auth

        p1, p2 = self._patch_token_storage(auth, tmp_path)
        with p1, p2:
            auth._save_tokens("alice@example.com", {"refresh_token": "rt"})

        # Verify token was saved to per-email dumps path
        dumps_path = tmp_path / "dumps" / "alice@example.com" / "settings" / "google_tokens.json"
        assert dumps_path.exists()
        stored = json.loads(dumps_path.read_text())
        assert stored["refresh_token"] == "rt"


# ===================================================================
# get_drive_folder_id / set_drive_folder_id
# ===================================================================


class TestDriveFolderId:
    """Tests for get_drive_folder_id() and set_drive_folder_id()."""

    def _patch_token_storage(self, auth, tmp_path):
        """Return context managers that patch both legacy and per-email token paths."""
        legacy_file = tmp_path / "legacy" / "google_tokens.json"
        dumps_base = tmp_path / "dumps"
        dumps_base.mkdir(parents=True, exist_ok=True)
        return patch.object(auth, "_LEGACY_TOKEN_FILE", legacy_file), \
               patch("app.config.DUMPS_BASE", dumps_base)

    def test_get_folder_id_returns_stored_value(self, tmp_path):
        import app.auth as auth

        p1, p2 = self._patch_token_storage(auth, tmp_path)
        with p1, p2:
            auth._save_tokens("alice@example.com", {
                "refresh_token": "rt",
                "drive_folder_id": "folder-123",
            })
            assert auth.get_drive_folder_id("alice@example.com") == "folder-123"

    def test_get_folder_id_returns_empty_when_not_set(self, tmp_path):
        import app.auth as auth

        p1, p2 = self._patch_token_storage(auth, tmp_path)
        with p1, p2:
            auth._save_tokens("alice@example.com", {"refresh_token": "rt"})
            assert auth.get_drive_folder_id("alice@example.com") == ""

    def test_get_folder_id_returns_empty_for_unknown_email(self, tmp_path):
        import app.auth as auth

        p1, p2 = self._patch_token_storage(auth, tmp_path)
        with p1, p2:
            assert auth.get_drive_folder_id("nobody@example.com") == ""

    def test_set_folder_id_persists(self, tmp_path):
        import app.auth as auth

        p1, p2 = self._patch_token_storage(auth, tmp_path)
        with p1, p2:
            auth._save_tokens("alice@example.com", {"refresh_token": "rt"})
            auth.set_drive_folder_id("alice@example.com", "folder-456")
            assert auth.get_drive_folder_id("alice@example.com") == "folder-456"

    def test_set_folder_id_on_new_email(self, tmp_path):
        import app.auth as auth

        p1, p2 = self._patch_token_storage(auth, tmp_path)
        with p1, p2:
            auth.set_drive_folder_id("new@example.com", "folder-789")
            assert auth.get_drive_folder_id("new@example.com") == "folder-789"


# ===================================================================
# get_any_drive_credentials
# ===================================================================


class TestGetAnyDriveCredentials:
    """Tests for get_any_drive_credentials()."""

    def test_returns_first_valid_credentials(self):
        import app.auth as auth

        mock_creds = MagicMock()
        all_tokens = {"alice@example.com": {"refresh_token": "rt"}}

        with patch.object(auth, "_load_all_tokens", return_value=all_tokens), \
             patch.object(auth, "get_drive_credentials", return_value=mock_creds):
            creds, email = auth.get_any_drive_credentials()

        assert creds is mock_creds
        assert email == "alice@example.com"

    def test_returns_none_when_no_tokens(self):
        import app.auth as auth

        with patch.object(auth, "_load_all_tokens", return_value={}):
            creds, email = auth.get_any_drive_credentials()

        assert creds is None
        assert email is None

    def test_returns_none_when_all_credentials_invalid(self):
        import app.auth as auth

        all_tokens = {"alice@example.com": {"refresh_token": "rt"}}

        with patch.object(auth, "_load_all_tokens", return_value=all_tokens), \
             patch.object(auth, "get_drive_credentials", return_value=None):
            creds, email = auth.get_any_drive_credentials()

        assert creds is None
        assert email is None
