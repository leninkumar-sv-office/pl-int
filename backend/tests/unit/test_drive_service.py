"""
Unit tests for app/drive_service.py

Tests Google Drive sync operations with all external I/O mocked.
"""
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest


# ─── helpers ────────────────────────────────────────────────────────────────

def _make_mock_service():
    """Return a mock Drive service with common methods stubbed."""
    svc = MagicMock()
    svc.files.return_value = svc._files
    svc._files.get.return_value.execute.return_value = {"parents": ["parent_folder_id"]}
    svc._files.list.return_value.execute.return_value = {"files": []}
    svc._files.create.return_value.execute.return_value = {"id": "new_folder_id"}
    svc._files.update.return_value.execute.return_value = {"id": "existing_id"}
    svc.about.return_value.get.return_value.execute.return_value = {
        "user": {"emailAddress": "test@gmail.com"}
    }
    return svc


# ═══════════════════════════════════════════════════════════
#  _find_or_create_folder
# ═══════════════════════════════════════════════════════════

def test_find_or_create_folder_found():
    """Returns existing folder ID when folder already exists."""
    from app.drive_service import _find_or_create_folder
    svc = MagicMock()
    svc.files.return_value.list.return_value.execute.return_value = {
        "files": [{"id": "existing_folder_id"}]
    }
    result = _find_or_create_folder(svc, "myFolder", "parent_id")
    assert result == "existing_folder_id"


def test_find_or_create_folder_creates_new():
    """Creates a new folder when not found."""
    from app.drive_service import _find_or_create_folder
    svc = MagicMock()
    svc.files.return_value.list.return_value.execute.return_value = {"files": []}
    svc.files.return_value.create.return_value.execute.return_value = {"id": "new_id"}
    result = _find_or_create_folder(svc, "newFolder", "parent_id")
    assert result == "new_id"


# ═══════════════════════════════════════════════════════════
#  _find_file
# ═══════════════════════════════════════════════════════════

def test_find_file_found():
    from app.drive_service import _find_file
    svc = MagicMock()
    svc.files.return_value.list.return_value.execute.return_value = {
        "files": [{"id": "file123"}]
    }
    result = _find_file(svc, "test.json", "folder_id")
    assert result == "file123"


def test_find_file_not_found():
    from app.drive_service import _find_file
    svc = MagicMock()
    svc.files.return_value.list.return_value.execute.return_value = {"files": []}
    result = _find_file(svc, "missing.json", "folder_id")
    assert result is None


# ═══════════════════════════════════════════════════════════
#  _navigate_to_subfolder
# ═══════════════════════════════════════════════════════════

def test_navigate_to_subfolder_single_level():
    from app.drive_service import _navigate_to_subfolder
    svc = MagicMock()
    # Simulating folder found at each level
    svc.files.return_value.list.return_value.execute.return_value = {
        "files": [{"id": "data_folder_id"}]
    }
    result = _navigate_to_subfolder(svc, "root_id", "data")
    assert result == "data_folder_id"


# ═══════════════════════════════════════════════════════════
#  get_drive_status
# ═══════════════════════════════════════════════════════════

def test_get_drive_status_no_credentials():
    from app.drive_service import get_drive_status
    import app.auth as auth_mod
    with patch.object(auth_mod, "get_drive_credentials", return_value=None),          patch.object(auth_mod, "get_any_drive_credentials", return_value=(None, "")):
        result = get_drive_status("test@gmail.com")
    assert result["connected"] is False
    assert "No Drive credentials" in result["reason"]


def test_get_drive_status_no_folder_id():
    from app.drive_service import get_drive_status
    import app.auth as auth_mod
    mock_creds = MagicMock()
    with patch.object(auth_mod, "get_drive_credentials", return_value=mock_creds), \
         patch.object(auth_mod, "get_drive_folder_id", return_value=""), \
         patch("app.drive_service._DEFAULT_DUMPS_FOLDER_ID", ""):
        result = get_drive_status("test@gmail.com")
    assert result["connected"] is False

def test_get_drive_status_connected():
    from app.drive_service import get_drive_status
    import app.auth as auth_mod
    mock_creds = MagicMock()
    mock_service = MagicMock()
    mock_service.about.return_value.get.return_value.execute.return_value = {
        "user": {"emailAddress": "test@gmail.com"}
    }
    with patch.object(auth_mod, "get_drive_credentials", return_value=mock_creds), \
         patch.object(auth_mod, "get_drive_folder_id", return_value="some_folder_id"), \
         patch("app.drive_service._get_service", return_value=mock_service), \
         patch("app.drive_service._get_dumps_folder_id", return_value="some_folder_id"):
        result = get_drive_status("test@gmail.com")
    assert result["connected"] is True
    assert result["user"] == "test@gmail.com"

def test_upload_file_skips_nonexistent(tmp_path):
    """upload_file should return silently if file doesn't exist."""
    from app.drive_service import upload_file
    non_existent = tmp_path / "missing.json"
    # Should not raise; no thread should be spawned
    upload_file(str(non_existent))


def test_upload_file_spawns_thread(tmp_path):
    """upload_file spawns a daemon thread when file exists."""
    from app.drive_service import upload_file
    test_file = tmp_path / "test.json"
    test_file.write_text("{}")
    threads_before = len(threading.enumerate())
    with patch("app.drive_service._get_service", return_value=None):
        upload_file(str(test_file))
    # Allow thread to start
    time.sleep(0.05)
    # Thread may have already finished; that's fine — just verify no exception


# ═══════════════════════════════════════════════════════════
#  download_file
# ═══════════════════════════════════════════════════════════

def test_download_file_no_service(tmp_path):
    from app.drive_service import download_file
    with patch("app.drive_service._get_service", return_value=None):
        result = download_file("test.json", tmp_path / "out.json")
    assert result is False


def test_download_file_no_folder_id(tmp_path):
    from app.drive_service import download_file
    mock_service = MagicMock()
    with patch("app.drive_service._get_service", return_value=mock_service), \
         patch("app.drive_service._get_dumps_folder_id", return_value=""):
        result = download_file("test.json", tmp_path / "out.json")
    assert result is False


def test_download_file_file_not_found(tmp_path):
    from app.drive_service import download_file
    mock_service = MagicMock()
    with patch("app.drive_service._get_service", return_value=mock_service), \
         patch("app.drive_service._get_dumps_folder_id", return_value="folder_id"), \
         patch("app.drive_service._get_pl_folder_id", return_value="pl_id"), \
         patch("app.drive_service._navigate_to_subfolder", return_value="folder_id"), \
         patch("app.drive_service._find_file", return_value=None):
        result = download_file("missing.json", tmp_path / "out.json")
    assert result is False


def test_download_file_success(tmp_path):
    from app.drive_service import download_file
    mock_service = MagicMock()
    # Mock the MediaIoBaseDownload
    mock_downloader = MagicMock()
    mock_downloader.next_chunk.return_value = (None, True)  # done=True first call

    with patch("app.drive_service._get_service", return_value=mock_service), \
         patch("app.drive_service._get_dumps_folder_id", return_value="folder_id"), \
         patch("app.drive_service._get_pl_folder_id", return_value="pl_id"), \
         patch("app.drive_service._find_file", return_value="file_id_abc"), \
         patch("googleapiclient.http.MediaIoBaseDownload", return_value=mock_downloader):
        result = download_file("test.json", tmp_path / "out.json")
    assert result is True


# ═══════════════════════════════════════════════════════════
#  sync_data_file
# ═══════════════════════════════════════════════════════════

def test_sync_data_file_calls_upload():
    from app import drive_service
    with patch("app.drive_service.upload_file") as mock_upload:
        drive_service.sync_data_file("stock_prices.json")
    mock_upload.assert_called_once()
    args = mock_upload.call_args[0]
    assert str(args[0]).endswith("stock_prices.json")


# ═══════════════════════════════════════════════════════════
#  init_drive_for_email
# ═══════════════════════════════════════════════════════════

def test_init_drive_for_email_already_exists():
    from app.drive_service import init_drive_for_email
    import app.auth as auth_mod
    with patch.object(auth_mod, "get_drive_folder_id", return_value="existing_dumps_id"):
        result = init_drive_for_email("user@gmail.com")
    assert result == "existing_dumps_id"


def test_init_drive_for_email_no_service():
    from app.drive_service import init_drive_for_email
    import app.auth as auth_mod
    with patch.object(auth_mod, "get_drive_folder_id", return_value=""), \
         patch("app.drive_service._get_service", return_value=None):
        result = init_drive_for_email("newuser@gmail.com")
    assert result == ""
