"""
Direct Google Drive read/write for settings JSON files.

All settings (expiry_rules, notification_prefs, user_settings) are stored
directly on Google Drive — no local files. In-memory cache avoids redundant
API calls. Cache refreshes on write or explicit invalidation.

Drive path: pl/dumps/{email}/{user_name}/settings/{filename}
"""
import io
import json
import logging
import threading
from typing import Optional

logger = logging.getLogger(__name__)

# In-memory cache: {(email, user_id, filename): data}
_cache = {}
_cache_lock = threading.Lock()


def _get_drive_subfolder(email: str, user_id: str) -> str:
    """Get Drive subfolder path for settings: dumps/{email}/{Name}/settings"""
    from .config import get_user_dumps_dir, DUMPS_BASE
    dumps_dir = get_user_dumps_dir(user_id, email)
    try:
        rel = dumps_dir.relative_to(DUMPS_BASE)
    except ValueError:
        rel = dumps_dir
    return "dumps/" + str(rel / "settings")


def read_json(email: str, user_id: str, filename: str, default=None):
    """Read a JSON settings file directly from Google Drive.

    Uses in-memory cache. Returns default if file not found or Drive unavailable.
    """
    cache_key = (email, user_id, filename)

    # Check memory cache first
    with _cache_lock:
        if cache_key in _cache:
            return _cache[cache_key]

    # Read from Drive
    try:
        from . import drive_service, auth
        service = drive_service._get_service(email)
        if not service:
            logger.debug(f"[DriveSettings] No Drive service for {email} — returning default")
            return default if default is not None else ([] if 'rules' in filename else {})

        dumps_folder_id = drive_service._get_dumps_folder_id(email)
        if not dumps_folder_id:
            return default if default is not None else ([] if 'rules' in filename else {})

        pl_id = drive_service._get_pl_folder_id(service, email)
        if not pl_id:
            return default if default is not None else ([] if 'rules' in filename else {})

        subfolder = _get_drive_subfolder(email, user_id)
        target_folder = drive_service._navigate_to_subfolder(service, pl_id, subfolder)

        file_id = drive_service._find_file(service, filename, target_folder)
        if not file_id:
            logger.debug(f"[DriveSettings] {filename} not found on Drive for {email}/{user_id}")
            result = default if default is not None else ([] if 'rules' in filename else {})
            with _cache_lock:
                _cache[cache_key] = result
            return result

        # Download content directly to memory (no local file)
        request = service.files().get_media(fileId=file_id)
        buffer = io.BytesIO()
        from googleapiclient.http import MediaIoBaseDownload
        downloader = MediaIoBaseDownload(buffer, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()

        buffer.seek(0)
        data = json.loads(buffer.read().decode("utf-8"))
        logger.info(f"[DriveSettings] Read {filename} from Drive ({email}/{user_id})")

        with _cache_lock:
            _cache[cache_key] = data
        return data

    except Exception as e:
        logger.error(f"[DriveSettings] Failed to read {filename} from Drive: {e}")
        return default if default is not None else ([] if 'rules' in filename else {})


def write_json(email: str, user_id: str, filename: str, data):
    """Write a JSON settings file directly to Google Drive.

    Updates in-memory cache immediately. Drive write is synchronous
    so the caller knows if it succeeded.
    """
    cache_key = (email, user_id, filename)

    # Update memory cache immediately
    with _cache_lock:
        _cache[cache_key] = data

    # Write to Drive
    try:
        from . import drive_service
        service = drive_service._get_service(email)
        if not service:
            logger.warning(f"[DriveSettings] No Drive service — {filename} cached in memory only")
            return False

        dumps_folder_id = drive_service._get_dumps_folder_id(email)
        if not dumps_folder_id:
            logger.warning(f"[DriveSettings] No dumps folder ID — {filename} cached in memory only")
            return False

        pl_id = drive_service._get_pl_folder_id(service, email)
        if not pl_id:
            return False

        subfolder = _get_drive_subfolder(email, user_id)
        target_folder = drive_service._navigate_to_subfolder(service, pl_id, subfolder)

        # Upload JSON content directly from memory
        content = json.dumps(data, indent=2).encode("utf-8")
        from googleapiclient.http import MediaInMemoryUpload
        media = MediaInMemoryUpload(content, mimetype="application/json")

        existing_id = drive_service._find_file(service, filename, target_folder)
        if existing_id:
            service.files().update(fileId=existing_id, media_body=media).execute()
        else:
            meta = {"name": filename, "parents": [target_folder]}
            service.files().create(body=meta, media_body=media, fields="id").execute()

        logger.info(f"[DriveSettings] Wrote {filename} to Drive ({email}/{user_id})")
        return True

    except Exception as e:
        logger.error(f"[DriveSettings] Failed to write {filename} to Drive: {e}")
        return False


def invalidate_cache(email: str = None, user_id: str = None, filename: str = None):
    """Clear cached settings to force re-read from Drive."""
    with _cache_lock:
        if email and user_id and filename:
            _cache.pop((email, user_id, filename), None)
        elif email:
            keys = [k for k in _cache if k[0] == email]
            for k in keys:
                del _cache[k]
        else:
            _cache.clear()
