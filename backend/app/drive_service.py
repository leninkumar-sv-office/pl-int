"""
Google Drive sync service.

Syncs data with Google Drive (leninkumar.sv.ai@gmail.com):
  My Drive/pl/
    ├── data/          (portfolio.json, users.json, etc.)
    └── dumps/         (per-user folders: Amma, Appa, Lenin)

On startup: downloads all files from Drive → local backend/dumps/
On writes:  uploads changed files from local → Drive (async)

Requires GOOGLE_DRIVE_DUMPS_FOLDER_ID env var pointing to the existing
"dumps" folder in Drive. The "pl" parent is discovered automatically.
"""
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

import logging
logger = logging.getLogger(__name__)

# Default "dumps" folder ID (legacy — used as fallback for existing email)
_DEFAULT_DUMPS_FOLDER_ID = os.getenv("GOOGLE_DRIVE_DUMPS_FOLDER_ID", "").strip()
DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# Cache for per-email parent "pl" folder IDs
_pl_folder_ids: dict[str, str] = {}

# Track sync state
_initial_sync_done = False


def _get_service(email: str = ""):
    """Build a Drive API service using stored credentials for an email."""
    from . import auth
    if email:
        creds = auth.get_drive_credentials(email)
    else:
        creds, _ = auth.get_any_drive_credentials()
    if not creds:
        return None
    from googleapiclient.discovery import build
    return build("drive", "v3", credentials=creds)


def _get_dumps_folder_id(email: str = "") -> str:
    """Get the Drive dumps folder ID for an email."""
    from . import auth
    if email:
        folder_id = auth.get_drive_folder_id(email)
        if folder_id:
            return folder_id
    return _DEFAULT_DUMPS_FOLDER_ID


def _get_pl_folder_id(service, email: str = "") -> Optional[str]:
    """Get the parent 'pl' folder ID from the known dumps folder."""
    cache_key = email or "_default"
    if cache_key in _pl_folder_ids:
        return _pl_folder_ids[cache_key]
    dumps_id = _get_dumps_folder_id(email)
    if not dumps_id:
        return None
    meta = service.files().get(fileId=dumps_id, fields="parents").execute()
    parents = meta.get("parents", [])
    if parents:
        _pl_folder_ids[cache_key] = parents[0]
        return parents[0]
    return None


def _find_or_create_folder(service, folder_name: str, parent_id: str) -> str:
    """Find a folder by name under parent, or create it. Returns folder ID."""
    q = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    if parent_id:
        q += f" and '{parent_id}' in parents"
    results = service.files().list(q=q, spaces="drive", fields="files(id)").execute()
    files = results.get("files", [])
    if files:
        return files[0]["id"]
    meta = {
        "name": folder_name,
        "mimeType": "application/vnd.google-apps.folder",
    }
    if parent_id:
        meta["parents"] = [parent_id]
    folder = service.files().create(body=meta, fields="id").execute()
    return folder["id"]


def _find_file(service, filename: str, folder_id: str) -> Optional[str]:
    """Find a file by name in a folder. Returns file ID or None."""
    q = f"name='{filename}' and '{folder_id}' in parents and trashed=false"
    results = service.files().list(q=q, spaces="drive", fields="files(id)").execute()
    files = results.get("files", [])
    return files[0]["id"] if files else None


def _navigate_to_subfolder(service, root_id: str, subfolder_path: str) -> str:
    """Navigate/create nested subfolders from root. Returns final folder ID."""
    current = root_id
    for part in Path(subfolder_path).parts:
        current = _find_or_create_folder(service, part, current)
    return current


def init_drive_for_email(email: str) -> str:
    """Create pl/dumps/ folder structure in a user's Drive. Returns dumps folder ID."""
    from . import auth
    existing = auth.get_drive_folder_id(email)
    if existing:
        return existing
    service = _get_service(email)
    if not service:
        logger.warning(f"[Drive] No credentials for {email} — cannot init folders")
        return ""
    try:
        # Create My Drive/pl/
        pl_id = _find_or_create_folder(service, "pl", "root")
        # Create My Drive/pl/data/
        _find_or_create_folder(service, "data", pl_id)
        # Create My Drive/pl/dumps/
        dumps_id = _find_or_create_folder(service, "dumps", pl_id)
        # Store the folder ID
        auth.set_drive_folder_id(email, dumps_id)
        _pl_folder_ids[email] = pl_id
        logger.info(f"[Drive] Initialized Drive folders for {email} (dumps={dumps_id})")
        return dumps_id
    except Exception as e:
        logger.error(f"[Drive] Failed to init Drive for {email}: {e}")
        return ""


def upload_file(local_path, subfolder: str = None, email: str = ""):
    """Upload a file to Drive (async). subfolder is relative to pl/ folder."""
    local_path = Path(local_path)
    if not local_path.exists():
        return

    def _do_upload():
        try:
            service = _get_service(email)
            if not service:
                return
            if not _get_dumps_folder_id(email):
                logger.warning(f"[Drive] No dumps folder ID for {email or 'default'}")
                return

            pl_id = _get_pl_folder_id(service, email)
            if not pl_id:
                logger.warning("[Drive] Could not find parent pl folder")
                return

            target_folder = pl_id
            if subfolder:
                target_folder = _navigate_to_subfolder(service, pl_id, subfolder)

            from googleapiclient.http import MediaFileUpload
            media = MediaFileUpload(str(local_path), resumable=True)
            existing_id = _find_file(service, local_path.name, target_folder)

            if existing_id:
                service.files().update(
                    fileId=existing_id, media_body=media
                ).execute()
            else:
                meta = {"name": local_path.name, "parents": [target_folder]}
                service.files().create(
                    body=meta, media_body=media, fields="id"
                ).execute()
            logger.info(f"[Drive] Uploaded {local_path.name}")
        except Exception as e:
            logger.error(f"[Drive] Upload failed for {local_path.name}: {e}")

    threading.Thread(target=_do_upload, daemon=True).start()


def delete_file(filename: str, subfolder: str = None, email: str = ""):
    """Delete a file from Drive (async). subfolder is relative to pl/ folder."""

    def _do_delete():
        try:
            service = _get_service(email)
            if not service:
                return
            if not _get_dumps_folder_id(email):
                return

            pl_id = _get_pl_folder_id(service, email)
            if not pl_id:
                return

            target_folder = pl_id
            if subfolder:
                target_folder = _navigate_to_subfolder(service, pl_id, subfolder)

            file_id = _find_file(service, filename, target_folder)
            if file_id:
                service.files().delete(fileId=file_id).execute()
                logger.info(f"[Drive] Deleted {filename}")
            else:
                logger.warning(f"[Drive] File not found for deletion: {filename}")
        except Exception as e:
            logger.error(f"[Drive] Delete failed for {filename}: {e}")

    threading.Thread(target=_do_delete, daemon=True).start()


def download_file(filename: str, local_path, subfolder: str = None, email: str = "") -> bool:
    """Download a file from Drive to local path. subfolder is relative to pl/."""
    local_path = Path(local_path)
    try:
        service = _get_service(email)
        if not service or not _get_dumps_folder_id(email):
            return False

        pl_id = _get_pl_folder_id(service, email)
        if not pl_id:
            return False

        target_folder = pl_id
        if subfolder:
            target_folder = _navigate_to_subfolder(service, pl_id, subfolder)

        file_id = _find_file(service, filename, target_folder)
        if not file_id:
            return False

        from googleapiclient.http import MediaIoBaseDownload
        request = service.files().get_media(fileId=file_id)
        local_path.parent.mkdir(parents=True, exist_ok=True)
        with open(local_path, "wb") as f:
            downloader = MediaIoBaseDownload(f, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()
        logger.info(f"[Drive] Downloaded {filename}")
        return True
    except Exception as e:
        logger.error(f"[Drive] Download failed for {filename}: {e}")
        return False


def _sync_folder_down(service, folder_id: str, local_dir: Path, depth: int = 0):
    """Recursively download all files from a Drive folder to a local directory.

    Downloads files that don't exist locally OR are newer on Drive.
    Uses modifiedTime from Drive API to compare with local mtime.
    """
    local_dir.mkdir(parents=True, exist_ok=True)
    q = f"'{folder_id}' in parents and trashed=false"
    # Paginate through all files (Drive API returns max 100 by default)
    page_token = None
    all_items = []
    while True:
        results = service.files().list(
            q=q, spaces="drive",
            fields="nextPageToken, files(id, name, mimeType, modifiedTime)",
            pageSize=1000,
            pageToken=page_token,
        ).execute()
        all_items.extend(results.get("files", []))
        page_token = results.get("nextPageToken")
        if not page_token:
            break

    downloaded = 0
    for item in all_items:
        local_path = local_dir / item["name"]
        if item["mimeType"] == "application/vnd.google-apps.folder":
            _sync_folder_down(service, item["id"], local_path, depth + 1)
        else:
            need_download = False
            if not local_path.exists():
                need_download = True
            else:
                # Compare Drive modifiedTime with local mtime
                try:
                    drive_mtime = datetime.fromisoformat(
                        item["modifiedTime"].replace("Z", "+00:00")
                    )
                    local_mtime = datetime.fromtimestamp(
                        local_path.stat().st_mtime, tz=timezone.utc
                    )
                    if drive_mtime > local_mtime:
                        need_download = True
                except Exception:
                    pass  # If we can't compare, skip — local is fine

            if need_download:
                try:
                    from googleapiclient.http import MediaIoBaseDownload
                    request = service.files().get_media(fileId=item["id"])
                    local_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(local_path, "wb") as f:
                        downloader = MediaIoBaseDownload(f, request)
                        done = False
                        while not done:
                            _, done = downloader.next_chunk()
                    downloaded += 1
                except Exception as e:
                    logger.error(f"[Drive] Failed to download {item['name']}: {e}")

    if downloaded > 0:
        indent = "  " * depth
        logger.info(f"[Drive] {indent}{local_dir.name}/: downloaded {downloaded} file(s)")


def sync_from_drive(email: str = ""):
    """Download data and dumps from Google Drive on startup."""
    global _initial_sync_done
    t0 = time.time()
    service = _get_service(email)
    if not service:
        logger.warning(f"[Drive] No credentials{f' for {email}' if email else ''} — skipping sync")
        return
    dumps_folder_id = _get_dumps_folder_id(email)
    if not dumps_folder_id:
        logger.warning(f"[Drive] No dumps folder ID for {email or 'default'} — skipping sync")
        return

    logger.info(f"[Drive] Syncing from Google Drive{f' ({email})' if email else ''}...")

    # Sync data/ from pl/data/
    pl_id = _get_pl_folder_id(service, email)
    if pl_id:
        try:
            data_folder_id = _find_or_create_folder(service, "data", pl_id)
            _sync_folder_down(service, data_folder_id, DATA_DIR)
        except Exception as e:
            logger.error(f"[Drive] Data sync failed: {e}")

    # Sync dumps/ from the email's pl/dumps/ folder
    from .config import DUMPS_BASE
    try:
        _sync_folder_down(service, dumps_folder_id, DUMPS_BASE)
    except Exception as e:
        logger.error(f"[Drive] Dumps sync failed: {e}")

    elapsed = time.time() - t0
    _initial_sync_done = True
    logger.info(f"[Drive] Sync from Drive complete ({elapsed:.1f}s)")


def sync_all_emails():
    """Sync Drive for all emails that have credentials stored."""
    from . import auth
    all_tokens = auth._load_all_tokens()
    if not all_tokens:
        logger.warning("[Drive] No stored credentials — skipping sync")
        return
    for email in all_tokens:
        if email:  # skip empty-key legacy entries
            sync_from_drive(email)


def sync_data_file(filename: str):
    """Upload a data file to pl/data/ on Drive."""
    local_path = DATA_DIR / filename
    upload_file(local_path, subfolder="data")


def sync_dumps_file(relative_path: str, email: str = ""):
    """Upload a dumps file to pl/dumps/... on Drive.

    relative_path: path relative to DUMPS_BASE, e.g. "email/Lenin/Stocks/TCS.xlsx"
    email: optional email for per-email Drive credentials
    """
    from .config import DUMPS_BASE
    local_path = DUMPS_BASE / relative_path
    parts = Path(relative_path).parts
    if len(parts) > 1:
        subfolder = "dumps/" + "/".join(parts[:-1])
    else:
        subfolder = "dumps"
    upload_file(local_path, subfolder=subfolder, email=email)


def get_drive_status(email: str = "") -> dict:
    """Check Drive sync status."""
    from . import auth
    if email:
        creds = auth.get_drive_credentials(email)
    else:
        creds, email = auth.get_any_drive_credentials()
    if not creds:
        return {"connected": False, "reason": "No Drive credentials — sign in with Google"}
    dumps_id = _get_dumps_folder_id(email)
    if not dumps_id:
        return {"connected": False, "reason": "No Drive folder configured for this account"}
    try:
        service = _get_service(email)
        about = service.about().get(fields="user").execute()
        return {
            "connected": True,
            "user": about["user"]["emailAddress"],
            "folder_id": dumps_id,
        }
    except Exception as e:
        return {"connected": False, "reason": str(e)}
