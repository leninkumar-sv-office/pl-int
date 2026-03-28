"""
Unit tests for app/drive_service.py

Tests Google Drive sync operations with all external I/O mocked.
"""
import json
import shutil
import threading
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest


# helpers

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


# _find_or_create_folder

def test_find_or_create_folder_found():
    from app.drive_service import _find_or_create_folder
    svc = MagicMock()
    svc.files.return_value.list.return_value.execute.return_value = {
        "files": [{"id": "existing_folder_id"}]
    }
    result = _find_or_create_folder(svc, "myFolder", "parent_id")
    assert result == "existing_folder_id"


def test_find_or_create_folder_creates_new():
    from app.drive_service import _find_or_create_folder
    svc = MagicMock()
    svc.files.return_value.list.return_value.execute.return_value = {"files": []}
    svc.files.return_value.create.return_value.execute.return_value = {"id": "new_id"}
    result = _find_or_create_folder(svc, "newFolder", "parent_id")
    assert result == "new_id"


def test_find_or_create_folder_no_parent():
    from app.drive_service import _find_or_create_folder
    svc = MagicMock()
    svc.files.return_value.list.return_value.execute.return_value = {"files": []}
    svc.files.return_value.create.return_value.execute.return_value = {"id": "new_id"}
    result = _find_or_create_folder(svc, "rootFolder", "")
    assert result == "new_id"


# _find_file

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


# _navigate_to_subfolder

def test_navigate_to_subfolder_single_level():
    from app.drive_service import _navigate_to_subfolder
    svc = MagicMock()
    svc.files.return_value.list.return_value.execute.return_value = {
        "files": [{"id": "data_folder_id"}]
    }
    result = _navigate_to_subfolder(svc, "root_id", "data")
    assert result == "data_folder_id"


def test_navigate_to_subfolder_nested():
    from app.drive_service import _navigate_to_subfolder
    svc = MagicMock()
    call_count = [0]
    folder_ids = ["level1_id", "level2_id"]

    def list_side_effect(*args, **kwargs):
        mock = MagicMock()
        idx = min(call_count[0], len(folder_ids) - 1)
        mock.execute.return_value = {"files": [{"id": folder_ids[idx]}]}
        call_count[0] += 1
        return mock

    svc.files.return_value.list.side_effect = list_side_effect
    result = _navigate_to_subfolder(svc, "root_id", "level1/level2")
    assert result == "level2_id"


# _get_pl_folder_id

def test_get_pl_folder_id_cached():
    from app import drive_service as ds
    ds._pl_folder_ids["test_cache"] = "cached_pl_id"
    try:
        result = ds._get_pl_folder_id(MagicMock(), "test_cache")
        assert result == "cached_pl_id"
    finally:
        del ds._pl_folder_ids["test_cache"]


def test_get_pl_folder_id_no_dumps_id():
    from app import drive_service as ds
    with patch("app.drive_service._get_dumps_folder_id", return_value=""):
        result = ds._get_pl_folder_id(MagicMock(), "no_dumps")
    assert result is None


def test_get_pl_folder_id_no_parents():
    from app import drive_service as ds
    svc = MagicMock()
    svc.files.return_value.get.return_value.execute.return_value = {"parents": []}
    with patch("app.drive_service._get_dumps_folder_id", return_value="dumps_id"):
        result = ds._get_pl_folder_id(svc, "no_parents_email")
    assert result is None


def test_get_pl_folder_id_success():
    from app import drive_service as ds
    svc = MagicMock()
    svc.files.return_value.get.return_value.execute.return_value = {"parents": ["pl_parent_id"]}
    with patch("app.drive_service._get_dumps_folder_id", return_value="dumps_id"):
        result = ds._get_pl_folder_id(svc, "success_email")
    assert result == "pl_parent_id"
    # Cleanup
    if "success_email" in ds._pl_folder_ids:
        del ds._pl_folder_ids["success_email"]


# _get_service

def test_get_service_with_email():
    from app import drive_service as ds
    mock_creds = MagicMock()
    with patch("app.auth.get_drive_credentials", return_value=mock_creds), \
         patch("googleapiclient.discovery.build", return_value="service_obj"):
        result = ds._get_service("test@gmail.com")
    assert result == "service_obj"


def test_get_service_no_email():
    from app import drive_service as ds
    mock_creds = MagicMock()
    with patch("app.auth.get_any_drive_credentials", return_value=(mock_creds, "test@gmail.com")), \
         patch("googleapiclient.discovery.build", return_value="service_obj"):
        result = ds._get_service("")
    assert result == "service_obj"


def test_get_service_no_creds():
    from app import drive_service as ds
    with patch("app.auth.get_drive_credentials", return_value=None):
        result = ds._get_service("nope@gmail.com")
    assert result is None


# _get_dumps_folder_id

def test_get_dumps_folder_id_with_email():
    from app import drive_service as ds
    with patch("app.auth.get_drive_folder_id", return_value="folder_123"):
        result = ds._get_dumps_folder_id("test@gmail.com")
    assert result == "folder_123"


def test_get_dumps_folder_id_fallback_default():
    from app import drive_service as ds
    with patch("app.auth.get_drive_folder_id", return_value=""), \
         patch.object(ds, "_DEFAULT_DUMPS_FOLDER_ID", "default_id"):
        result = ds._get_dumps_folder_id("test@gmail.com")
    assert result == "default_id"


# get_drive_status

def test_get_drive_status_no_credentials():
    from app.drive_service import get_drive_status
    import app.auth as auth_mod
    with patch.object(auth_mod, "get_drive_credentials", return_value=None), \
         patch.object(auth_mod, "get_any_drive_credentials", return_value=(None, "")):
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


def test_get_drive_status_no_email_fallback():
    from app.drive_service import get_drive_status
    import app.auth as auth_mod
    mock_creds = MagicMock()
    mock_service = MagicMock()
    mock_service.about.return_value.get.return_value.execute.return_value = {
        "user": {"emailAddress": "default@gmail.com"}
    }
    with patch.object(auth_mod, "get_any_drive_credentials", return_value=(mock_creds, "default@gmail.com")), \
         patch("app.drive_service._get_service", return_value=mock_service), \
         patch("app.drive_service._get_dumps_folder_id", return_value="folder_id"):
        result = get_drive_status("")
    assert result["connected"] is True


def test_get_drive_status_api_exception():
    from app.drive_service import get_drive_status
    import app.auth as auth_mod
    mock_creds = MagicMock()
    mock_service = MagicMock()
    mock_service.about.return_value.get.return_value.execute.side_effect = Exception("API error")
    with patch.object(auth_mod, "get_drive_credentials", return_value=mock_creds), \
         patch.object(auth_mod, "get_drive_folder_id", return_value="folder_id"), \
         patch("app.drive_service._get_service", return_value=mock_service), \
         patch("app.drive_service._get_dumps_folder_id", return_value="folder_id"):
        result = get_drive_status("test@gmail.com")
    assert result["connected"] is False
    assert "API error" in result["reason"]


# upload_file

def test_upload_file_skips_nonexistent(tmp_path):
    from app.drive_service import upload_file
    non_existent = tmp_path / "missing.json"
    upload_file(str(non_existent))


def test_upload_file_spawns_thread(tmp_path):
    from app.drive_service import upload_file
    test_file = tmp_path / "test.json"
    test_file.write_text("{}")
    with patch("app.drive_service._get_service", return_value=None):
        upload_file(str(test_file))
    time.sleep(0.05)


def test_upload_file_update_existing(tmp_path):
    from app.drive_service import upload_file
    test_file = tmp_path / "test.json"
    test_file.write_text("{}")
    mock_service = MagicMock()
    mock_service.files.return_value.get.return_value.execute.return_value = {"parents": ["pl_id"]}
    mock_service.files.return_value.list.return_value.execute.return_value = {"files": [{"id": "existing_file_id"}]}
    mock_service.files.return_value.update.return_value.execute.return_value = {"id": "existing_file_id"}

    with patch("app.drive_service._get_service", return_value=mock_service), \
         patch("app.drive_service._get_dumps_folder_id", return_value="dumps_id"), \
         patch("app.drive_service._get_pl_folder_id", return_value="pl_id"), \
         patch("app.drive_service._find_file", return_value="existing_file_id"), \
         patch("googleapiclient.http.MediaFileUpload"):
        upload_file(str(test_file), subfolder="data")
    time.sleep(0.1)


def test_upload_file_create_new(tmp_path):
    from app.drive_service import upload_file
    test_file = tmp_path / "new.json"
    test_file.write_text("{}")
    mock_service = MagicMock()
    mock_service.files.return_value.create.return_value.execute.return_value = {"id": "new_file_id"}

    with patch("app.drive_service._get_service", return_value=mock_service), \
         patch("app.drive_service._get_dumps_folder_id", return_value="dumps_id"), \
         patch("app.drive_service._get_pl_folder_id", return_value="pl_id"), \
         patch("app.drive_service._find_file", return_value=None), \
         patch("googleapiclient.http.MediaFileUpload"):
        upload_file(str(test_file))
    time.sleep(0.1)


def test_upload_file_no_pl_folder(tmp_path):
    from app.drive_service import upload_file
    test_file = tmp_path / "test.json"
    test_file.write_text("{}")
    with patch("app.drive_service._get_service", return_value=MagicMock()), \
         patch("app.drive_service._get_dumps_folder_id", return_value="dumps_id"), \
         patch("app.drive_service._get_pl_folder_id", return_value=None):
        upload_file(str(test_file))
    time.sleep(0.05)


def test_upload_file_no_dumps_folder_id(tmp_path):
    from app.drive_service import upload_file
    test_file = tmp_path / "test.json"
    test_file.write_text("{}")
    with patch("app.drive_service._get_service", return_value=MagicMock()), \
         patch("app.drive_service._get_dumps_folder_id", return_value=""):
        upload_file(str(test_file))
    time.sleep(0.05)


def test_upload_file_exception(tmp_path):
    from app.drive_service import upload_file
    test_file = tmp_path / "test.json"
    test_file.write_text("{}")
    with patch("app.drive_service._get_service", side_effect=Exception("err")):
        upload_file(str(test_file))
    time.sleep(0.05)


# delete_file

def test_delete_file_success(tmp_path):
    from app.drive_service import delete_file
    mock_service = MagicMock()
    with patch("app.drive_service._get_service", return_value=mock_service), \
         patch("app.drive_service._get_dumps_folder_id", return_value="dumps_id"), \
         patch("app.drive_service._get_pl_folder_id", return_value="pl_id"), \
         patch("app.drive_service._find_file", return_value="file_to_delete"):
        delete_file("old.json")
    time.sleep(0.1)


def test_delete_file_not_found(tmp_path):
    from app.drive_service import delete_file
    mock_service = MagicMock()
    with patch("app.drive_service._get_service", return_value=mock_service), \
         patch("app.drive_service._get_dumps_folder_id", return_value="dumps_id"), \
         patch("app.drive_service._get_pl_folder_id", return_value="pl_id"), \
         patch("app.drive_service._find_file", return_value=None):
        delete_file("missing.json")
    time.sleep(0.05)


def test_delete_file_no_service():
    from app.drive_service import delete_file
    with patch("app.drive_service._get_service", return_value=None):
        delete_file("x.json")
    time.sleep(0.05)


def test_delete_file_no_dumps_id():
    from app.drive_service import delete_file
    with patch("app.drive_service._get_service", return_value=MagicMock()), \
         patch("app.drive_service._get_dumps_folder_id", return_value=""):
        delete_file("x.json")
    time.sleep(0.05)


def test_delete_file_no_pl_folder():
    from app.drive_service import delete_file
    with patch("app.drive_service._get_service", return_value=MagicMock()), \
         patch("app.drive_service._get_dumps_folder_id", return_value="dumps_id"), \
         patch("app.drive_service._get_pl_folder_id", return_value=None):
        delete_file("x.json")
    time.sleep(0.05)


def test_delete_file_with_subfolder():
    from app.drive_service import delete_file
    mock_service = MagicMock()
    with patch("app.drive_service._get_service", return_value=mock_service), \
         patch("app.drive_service._get_dumps_folder_id", return_value="dumps_id"), \
         patch("app.drive_service._get_pl_folder_id", return_value="pl_id"), \
         patch("app.drive_service._navigate_to_subfolder", return_value="sub_id"), \
         patch("app.drive_service._find_file", return_value="fid"):
        delete_file("old.json", subfolder="data")
    time.sleep(0.1)


def test_delete_file_exception():
    from app.drive_service import delete_file
    with patch("app.drive_service._get_service", return_value=MagicMock()), \
         patch("app.drive_service._get_dumps_folder_id", return_value="d"), \
         patch("app.drive_service._get_pl_folder_id", side_effect=Exception("err")):
        delete_file("x.json")
    time.sleep(0.05)


# download_file

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


def test_download_file_no_pl_folder(tmp_path):
    from app.drive_service import download_file
    with patch("app.drive_service._get_service", return_value=MagicMock()), \
         patch("app.drive_service._get_dumps_folder_id", return_value="dumps"), \
         patch("app.drive_service._get_pl_folder_id", return_value=None):
        result = download_file("test.json", tmp_path / "out.json")
    assert result is False


def test_download_file_file_not_found(tmp_path):
    from app.drive_service import download_file
    with patch("app.drive_service._get_service", return_value=MagicMock()), \
         patch("app.drive_service._get_dumps_folder_id", return_value="folder_id"), \
         patch("app.drive_service._get_pl_folder_id", return_value="pl_id"), \
         patch("app.drive_service._navigate_to_subfolder", return_value="folder_id"), \
         patch("app.drive_service._find_file", return_value=None):
        result = download_file("missing.json", tmp_path / "out.json")
    assert result is False


def test_download_file_success(tmp_path):
    from app.drive_service import download_file
    mock_service = MagicMock()
    mock_downloader = MagicMock()
    mock_downloader.next_chunk.return_value = (None, True)

    with patch("app.drive_service._get_service", return_value=mock_service), \
         patch("app.drive_service._get_dumps_folder_id", return_value="folder_id"), \
         patch("app.drive_service._get_pl_folder_id", return_value="pl_id"), \
         patch("app.drive_service._find_file", return_value="file_id_abc"), \
         patch("googleapiclient.http.MediaIoBaseDownload", return_value=mock_downloader):
        result = download_file("test.json", tmp_path / "out.json")
    assert result is True


def test_download_file_with_subfolder(tmp_path):
    from app.drive_service import download_file
    mock_service = MagicMock()
    mock_downloader = MagicMock()
    mock_downloader.next_chunk.return_value = (None, True)

    with patch("app.drive_service._get_service", return_value=mock_service), \
         patch("app.drive_service._get_dumps_folder_id", return_value="folder_id"), \
         patch("app.drive_service._get_pl_folder_id", return_value="pl_id"), \
         patch("app.drive_service._navigate_to_subfolder", return_value="sub_id"), \
         patch("app.drive_service._find_file", return_value="fid"), \
         patch("googleapiclient.http.MediaIoBaseDownload", return_value=mock_downloader):
        result = download_file("test.json", tmp_path / "out.json", subfolder="data")
    assert result is True


def test_download_file_exception(tmp_path):
    from app.drive_service import download_file
    with patch("app.drive_service._get_service", return_value=MagicMock()), \
         patch("app.drive_service._get_dumps_folder_id", return_value="d"), \
         patch("app.drive_service._get_pl_folder_id", side_effect=Exception("err")):
        result = download_file("x.json", tmp_path / "out.json")
    assert result is False


# sync_data_file

def test_sync_data_file_calls_upload():
    from app import drive_service
    with patch("app.drive_service.upload_file") as mock_upload:
        drive_service.sync_data_file("stock_prices.json")
    mock_upload.assert_called_once()
    args = mock_upload.call_args[0]
    assert str(args[0]).endswith("stock_prices.json")


# sync_dumps_file

def test_sync_dumps_file_with_subfolder():
    from app import drive_service
    with patch("app.drive_service.upload_file") as mock_upload, \
         patch("app.config.DUMPS_BASE", Path("/fake/dumps")):
        drive_service.sync_dumps_file("test@x.com/Lenin/Stocks/TCS.xlsx", email="test@x.com")
    mock_upload.assert_called_once()
    kwargs = mock_upload.call_args[1]
    assert "dumps/" in kwargs["subfolder"]


def test_sync_dumps_file_single_file():
    from app import drive_service
    with patch("app.drive_service.upload_file") as mock_upload, \
         patch("app.config.DUMPS_BASE", Path("/fake/dumps")):
        drive_service.sync_dumps_file("singlefile.json")
    kwargs = mock_upload.call_args[1]
    assert kwargs["subfolder"] == "dumps"


# init_drive_for_email

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


def test_init_drive_for_email_creates_folders():
    from app.drive_service import init_drive_for_email
    import app.auth as auth_mod
    mock_service = MagicMock()
    mock_service.files.return_value.list.return_value.execute.return_value = {"files": []}
    mock_service.files.return_value.create.return_value.execute.return_value = {"id": "new_dumps_id"}

    with patch.object(auth_mod, "get_drive_folder_id", return_value=""), \
         patch("app.drive_service._get_service", return_value=mock_service), \
         patch("app.drive_service._find_or_create_folder", return_value="new_folder_id"), \
         patch.object(auth_mod, "set_drive_folder_id"):
        result = init_drive_for_email("new@gmail.com")
    assert result == "new_folder_id"


def test_init_drive_for_email_exception():
    from app.drive_service import init_drive_for_email
    import app.auth as auth_mod
    mock_service = MagicMock()
    with patch.object(auth_mod, "get_drive_folder_id", return_value=""), \
         patch("app.drive_service._get_service", return_value=mock_service), \
         patch("app.drive_service._find_or_create_folder", side_effect=Exception("err")):
        result = init_drive_for_email("error@gmail.com")
    assert result == ""


# _sync_folder_down

def test_sync_folder_down_downloads_file(tmp_path):
    from app.drive_service import _sync_folder_down
    svc = MagicMock()
    svc.files.return_value.list.return_value.execute.return_value = {
        "files": [
            {"id": "f1", "name": "test.json", "mimeType": "application/json",
             "modifiedTime": "2026-01-01T00:00:00Z"}
        ],
        "nextPageToken": None,
    }
    mock_dl = MagicMock()
    mock_dl.next_chunk.return_value = (None, True)

    with patch("googleapiclient.http.MediaIoBaseDownload", return_value=mock_dl):
        _sync_folder_down(svc, "folder_id", tmp_path)


def test_sync_folder_down_skips_up_to_date(tmp_path):
    from app.drive_service import _sync_folder_down
    # Create local file with recent mtime
    local_file = tmp_path / "existing.json"
    local_file.write_text("{}")

    svc = MagicMock()
    # Drive file modified in the past
    svc.files.return_value.list.return_value.execute.return_value = {
        "files": [
            {"id": "f1", "name": "existing.json", "mimeType": "application/json",
             "modifiedTime": "2020-01-01T00:00:00Z"}
        ],
        "nextPageToken": None,
    }
    _sync_folder_down(svc, "folder_id", tmp_path)


def test_sync_folder_down_removes_stale_local(tmp_path):
    from app.drive_service import _sync_folder_down
    stale_file = tmp_path / "stale.txt"
    stale_file.write_text("stale")

    svc = MagicMock()
    svc.files.return_value.list.return_value.execute.return_value = {
        "files": [],
        "nextPageToken": None,
    }
    _sync_folder_down(svc, "folder_id", tmp_path)
    assert not stale_file.exists()


def test_sync_folder_down_skips_hidden_files(tmp_path):
    from app.drive_service import _sync_folder_down
    hidden = tmp_path / ".hidden"
    hidden.write_text("hidden")
    cache_dir = tmp_path / "__pycache__"
    cache_dir.mkdir()

    svc = MagicMock()
    svc.files.return_value.list.return_value.execute.return_value = {
        "files": [],
        "nextPageToken": None,
    }
    _sync_folder_down(svc, "folder_id", tmp_path)
    assert hidden.exists()
    assert cache_dir.exists()


def test_sync_folder_down_recurse_folders(tmp_path):
    from app.drive_service import _sync_folder_down
    svc = MagicMock()
    call_count = [0]

    def list_side_effect(*args, **kwargs):
        mock = MagicMock()
        if call_count[0] == 0:
            mock.execute.return_value = {
                "files": [{"id": "subfolder1", "name": "sub",
                           "mimeType": "application/vnd.google-apps.folder",
                           "modifiedTime": "2026-01-01T00:00:00Z"}],
                "nextPageToken": None,
            }
        else:
            mock.execute.return_value = {"files": [], "nextPageToken": None}
        call_count[0] += 1
        return mock

    svc.files.return_value.list.side_effect = list_side_effect
    _sync_folder_down(svc, "root_id", tmp_path)
    assert (tmp_path / "sub").is_dir()


# sync_from_drive

def test_sync_from_drive_no_service():
    from app.drive_service import sync_from_drive
    with patch("app.drive_service._get_service", return_value=None):
        sync_from_drive("test@gmail.com")


def test_sync_from_drive_no_dumps_folder():
    from app.drive_service import sync_from_drive
    with patch("app.drive_service._get_service", return_value=MagicMock()), \
         patch("app.drive_service._get_dumps_folder_id", return_value=""):
        sync_from_drive("test@gmail.com")


def test_sync_from_drive_success():
    from app.drive_service import sync_from_drive
    mock_service = MagicMock()
    with patch("app.drive_service._get_service", return_value=mock_service), \
         patch("app.drive_service._get_dumps_folder_id", return_value="dumps_id"), \
         patch("app.drive_service._get_pl_folder_id", return_value="pl_id"), \
         patch("app.drive_service._find_or_create_folder", return_value="data_id"), \
         patch("app.drive_service._sync_folder_down") as mock_sync, \
         patch("app.config.DUMPS_BASE", Path("/tmp/test_dumps")):
        sync_from_drive("test@gmail.com")
        assert mock_sync.call_count == 2  # data + dumps


def test_sync_from_drive_data_exception():
    from app.drive_service import sync_from_drive
    mock_service = MagicMock()
    with patch("app.drive_service._get_service", return_value=mock_service), \
         patch("app.drive_service._get_dumps_folder_id", return_value="dumps_id"), \
         patch("app.drive_service._get_pl_folder_id", return_value="pl_id"), \
         patch("app.drive_service._find_or_create_folder", side_effect=Exception("err")), \
         patch("app.drive_service._sync_folder_down") as mock_sync, \
         patch("app.config.DUMPS_BASE", Path("/tmp/test_dumps")):
        sync_from_drive("test@gmail.com")


# sync_all_emails

def test_sync_all_emails_no_tokens():
    from app.drive_service import sync_all_emails
    with patch("app.auth._load_all_tokens", return_value={}):
        sync_all_emails()


def test_sync_all_emails_with_tokens():
    from app.drive_service import sync_all_emails
    with patch("app.auth._load_all_tokens", return_value={"a@b.com": {}, "": {}}), \
         patch("app.drive_service.sync_from_drive") as mock_sync:
        sync_all_emails()
        mock_sync.assert_called_once_with("a@b.com")  # Empty key skipped
