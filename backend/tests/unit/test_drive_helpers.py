"""
Tests for _sync_to_drive and _delete_from_drive across all database modules.

These functions are mocked by autouse fixtures in their respective test files,
so they need separate tests without the autouse mock to achieve coverage.
"""
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


# ═══════════════════════════════════════════════════════════
#  _sync_to_drive — all modules (simple no-op: `pass`)
# ═══════════════════════════════════════════════════════════

def test_fd_sync_to_drive():
    from app.fd_database import _sync_to_drive
    _sync_to_drive(Path("/tmp/test.xlsx"))


def test_rd_sync_to_drive():
    from app.rd_database import _sync_to_drive
    _sync_to_drive(Path("/tmp/test.xlsx"))


def test_ppf_sync_to_drive():
    from app.ppf_database import _sync_to_drive
    _sync_to_drive(Path("/tmp/test.xlsx"))


def test_nps_sync_to_drive():
    from app.nps_database import _sync_to_drive
    _sync_to_drive(Path("/tmp/test.xlsx"))


def test_si_sync_to_drive():
    from app.si_database import _sync_to_drive
    _sync_to_drive(Path("/tmp/test.xlsx"))


def test_insurance_sync_to_drive():
    from app.insurance_database import _sync_to_drive
    _sync_to_drive(Path("/tmp/test.json"))


# ═══════════════════════════════════════════════════════════
#  _delete_from_drive — all modules (tries drive_service.delete_file)
# ═══════════════════════════════════════════════════════════

def test_fd_delete_from_drive_success(tmp_path):
    from app.fd_database import _delete_from_drive
    # Create a file structure that resolves relative to DUMPS_BASE
    dumps_base = tmp_path / "dumps"
    email_dir = dumps_base / "test@example.com" / "TestUser" / "FD"
    email_dir.mkdir(parents=True)
    filepath = email_dir / "test.xlsx"
    filepath.write_text("test")

    with patch("app.config.DUMPS_BASE", dumps_base), \
         patch("app.drive_service.delete_file") as mock_del:
        _delete_from_drive(filepath)
    mock_del.assert_called_once()


def test_fd_delete_from_drive_exception():
    from app.fd_database import _delete_from_drive
    # Non-existent path triggers exception which is swallowed
    _delete_from_drive(Path("/nonexistent/path/file.xlsx"))


def test_rd_delete_from_drive_success(tmp_path):
    from app.rd_database import _delete_from_drive
    dumps_base = tmp_path / "dumps"
    email_dir = dumps_base / "test@example.com" / "TestUser" / "RD"
    email_dir.mkdir(parents=True)
    filepath = email_dir / "test.xlsx"
    filepath.write_text("test")

    with patch("app.config.DUMPS_BASE", dumps_base), \
         patch("app.drive_service.delete_file") as mock_del:
        _delete_from_drive(filepath)
    mock_del.assert_called_once()


def test_rd_delete_from_drive_exception():
    from app.rd_database import _delete_from_drive
    _delete_from_drive(Path("/nonexistent/path/file.xlsx"))


def test_ppf_delete_from_drive_success(tmp_path):
    from app.ppf_database import _delete_from_drive
    dumps_base = tmp_path / "dumps"
    email_dir = dumps_base / "test@example.com" / "TestUser" / "PPF"
    email_dir.mkdir(parents=True)
    filepath = email_dir / "test.xlsx"
    filepath.write_text("test")

    with patch("app.config.DUMPS_BASE", dumps_base), \
         patch("app.drive_service.delete_file") as mock_del:
        _delete_from_drive(filepath)
    mock_del.assert_called_once()


def test_ppf_delete_from_drive_exception():
    from app.ppf_database import _delete_from_drive
    _delete_from_drive(Path("/nonexistent/path/file.xlsx"))


def test_nps_delete_from_drive_success(tmp_path):
    from app.nps_database import _delete_from_drive
    dumps_base = tmp_path / "dumps"
    email_dir = dumps_base / "test@example.com" / "TestUser" / "NPS"
    email_dir.mkdir(parents=True)
    filepath = email_dir / "test.xlsx"
    filepath.write_text("test")

    with patch("app.config.DUMPS_BASE", dumps_base), \
         patch("app.drive_service.delete_file") as mock_del:
        _delete_from_drive(filepath)
    mock_del.assert_called_once()


def test_nps_delete_from_drive_exception():
    from app.nps_database import _delete_from_drive
    _delete_from_drive(Path("/nonexistent/path/file.xlsx"))


def test_si_delete_from_drive_success(tmp_path):
    from app.si_database import _delete_from_drive
    dumps_base = tmp_path / "dumps"
    email_dir = dumps_base / "test@example.com" / "SI"
    email_dir.mkdir(parents=True)
    filepath = email_dir / "test.xlsx"
    filepath.write_text("test")

    with patch("app.config.DUMPS_BASE", dumps_base), \
         patch("app.drive_service.delete_file") as mock_del:
        _delete_from_drive(filepath)
    mock_del.assert_called_once()


def test_si_delete_from_drive_exception():
    from app.si_database import _delete_from_drive
    _delete_from_drive(Path("/nonexistent/path/file.xlsx"))


def test_insurance_delete_from_drive_success(tmp_path):
    from app.insurance_database import _delete_from_drive
    dumps_base = tmp_path / "dumps"
    email_dir = dumps_base / "test@example.com" / "Insurance"
    email_dir.mkdir(parents=True)
    filepath = email_dir / "test.json"
    filepath.write_text("test")

    with patch("app.config.DUMPS_BASE", dumps_base), \
         patch("app.drive_service.delete_file") as mock_del:
        _delete_from_drive(filepath)
    mock_del.assert_called_once()


def test_insurance_delete_from_drive_exception():
    from app.insurance_database import _delete_from_drive
    _delete_from_drive(Path("/nonexistent/path/file.json"))


# ═══════════════════════════════════════════════════════════
#  _delete_from_drive — single-part path (subfolder="dumps")
# ═══════════════════════════════════════════════════════════

def test_fd_delete_from_drive_single_part(tmp_path):
    """When filepath resolves to a single-part relative path, subfolder='dumps'."""
    from app.fd_database import _delete_from_drive
    dumps_base = tmp_path
    filepath = tmp_path / "test.xlsx"
    filepath.write_text("test")

    with patch("app.config.DUMPS_BASE", dumps_base), \
         patch("app.drive_service.delete_file") as mock_del:
        _delete_from_drive(filepath)
    # subfolder should be "dumps" for single-part path
    mock_del.assert_called_once_with("test.xlsx", subfolder="dumps", email="")


def test_si_delete_from_drive_single_part(tmp_path):
    """SI: single-part relative path => subfolder='dumps'."""
    from app.si_database import _delete_from_drive
    dumps_base = tmp_path
    filepath = tmp_path / "test.xlsx"
    filepath.write_text("test")

    with patch("app.config.DUMPS_BASE", dumps_base), \
         patch("app.drive_service.delete_file") as mock_del:
        _delete_from_drive(filepath)
    mock_del.assert_called_once_with("test.xlsx", subfolder="dumps", email="")


def test_insurance_delete_from_drive_single_part(tmp_path):
    """Insurance: single-part relative path => subfolder='dumps'."""
    from app.insurance_database import _delete_from_drive
    dumps_base = tmp_path
    filepath = tmp_path / "test.json"
    filepath.write_text("test")

    with patch("app.config.DUMPS_BASE", dumps_base), \
         patch("app.drive_service.delete_file") as mock_del:
        _delete_from_drive(filepath)
    mock_del.assert_called_once_with("test.json", subfolder="dumps", email="")


def test_rd_delete_from_drive_single_part(tmp_path):
    """RD: single-part relative path => subfolder='dumps'."""
    from app.rd_database import _delete_from_drive
    dumps_base = tmp_path
    filepath = tmp_path / "test.xlsx"
    filepath.write_text("test")

    with patch("app.config.DUMPS_BASE", dumps_base), \
         patch("app.drive_service.delete_file") as mock_del:
        _delete_from_drive(filepath)
    mock_del.assert_called_once_with("test.xlsx", subfolder="dumps", email="")


def test_ppf_delete_from_drive_single_part(tmp_path):
    """PPF: single-part relative path => subfolder='dumps'."""
    from app.ppf_database import _delete_from_drive
    dumps_base = tmp_path
    filepath = tmp_path / "test.xlsx"
    filepath.write_text("test")

    with patch("app.config.DUMPS_BASE", dumps_base), \
         patch("app.drive_service.delete_file") as mock_del:
        _delete_from_drive(filepath)
    mock_del.assert_called_once_with("test.xlsx", subfolder="dumps", email="")


def test_nps_delete_from_drive_single_part(tmp_path):
    """NPS: single-part relative path => subfolder='dumps'."""
    from app.nps_database import _delete_from_drive
    dumps_base = tmp_path
    filepath = tmp_path / "test.xlsx"
    filepath.write_text("test")

    with patch("app.config.DUMPS_BASE", dumps_base), \
         patch("app.drive_service.delete_file") as mock_del:
        _delete_from_drive(filepath)
    mock_del.assert_called_once_with("test.xlsx", subfolder="dumps", email="")
