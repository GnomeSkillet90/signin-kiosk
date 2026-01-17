#!/usr/bin/env python3
import sys
import mimetypes
from datetime import datetime
from pathlib import Path
import os
import getpass

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from tqdm import tqdm


def pick_storage_base():
    """
    Prefer the specific USB mount /media/<user>/USB if present & writable.
    Otherwise, fall back to any writable auto-mounted drive.
    Otherwise, fall back to SD (project folder).
    """
    user = getpass.getuser()

    preferred = f"/media/{user}/USB"
    if os.path.isdir(preferred) and os.access(preferred, os.W_OK):
        base = os.path.join(preferred, "signin_kiosk_data")
        try:
            os.makedirs(base, exist_ok=True)
            return base
        except Exception:
            pass

    for root in (f"/media/{user}", f"/run/media/{user}"):
        if not os.path.isdir(root):
            continue
        try:
            for name in os.listdir(root):
                mount_path = os.path.join(root, name)
                if os.path.isdir(mount_path) and os.access(mount_path, os.W_OK):
                    base = os.path.join(mount_path, "signin_kiosk_data")
                    try:
                        os.makedirs(base, exist_ok=True)
                        return base
                    except Exception:
                        pass
        except Exception:
            pass

    # Fallback: script location /signin_kiosk_data
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "signin_kiosk_data"))


# ===== CONFIG =====
SERVICE_ACCOUNT_JSON = "/home/gnomeskillet/.config/kiosk/drive_sa.json"

# Paste your Google Drive destination folder ID here
# Example URL: https://drive.google.com/drive/folders/<THIS_PART_IS_THE_ID>
DRIVE_PARENT_FOLDER_ID = "1U5yX5W8XKWeorNkZwH4M7AvnSW3aF23K"

# This folder contains your dated folders (YYYY-MM-DD)
LOCAL_BASE_DATA_DIR = pick_storage_base()
#print(f"[INFO] Using LOCAL_BASE_DATA_DIR: {LOCAL_BASE_DATA_DIR}")

# ==================

SCOPES = ["https://www.googleapis.com/auth/drive"]

def find_child_by_name(service, parent_id: str, name: str):
    """
    Return (file_id, mimeType) of an item named `name` directly under `parent_id`,
    or (None, None) if not found.
    """
    q = f"'{parent_id}' in parents and name='{name}' and trashed=false"
    res = service.files().list(
        q=q,
        fields="files(id,name,mimeType)",
        pageSize=10,
        supportsAllDrives=True,
        includeItemsFromAllDrives=True
    ).execute()
    files = res.get("files", [])
    if not files:
        return None, None

    # If duplicates already exist, just use the first one.
    # (Optional: you could later clean extras.)
    return files[0]["id"], files[0]["mimeType"]

def count_files_recursive(local_dir: Path) -> int:
    return sum(1 for p in local_dir.rglob("*") if p.is_file())

def get_drive_service():
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_JSON, scopes=SCOPES
    )
    return build("drive", "v3", credentials=creds)


def ensure_drive_folder(service, name: str, parent_id: str) -> str:
    """Find or create a folder named `name` under `parent_id` and return its ID."""
    q = (
        "mimeType='application/vnd.google-apps.folder' and "
        f"name='{name}' and '{parent_id}' in parents and trashed=false"
    )
    res = service.files().list(
        q=q,
        fields="files(id,name)",
        pageSize=10,
        supportsAllDrives=True,
        includeItemsFromAllDrives=True
    ).execute()

    files = res.get("files", [])
    if files:
        return files[0]["id"]

    meta = {
        "name": name,
        "mimeType": "application/vnd.google-apps.folder",
        "parents": [parent_id],
    }
    created = service.files().create(
        body=meta,
        fields="id",
        supportsAllDrives=True
    ).execute()

    return created["id"]


def upload_file(service, local_path: Path, parent_id: str, overwrite: bool = False):
    mime, _ = mimetypes.guess_type(str(local_path))
    if not mime:
        mime = "application/octet-stream"

    existing_id, _ = find_child_by_name(service, parent_id, local_path.name)

    media = MediaFileUpload(str(local_path), mimetype=mime, resumable=True)

    if existing_id and overwrite:
        # Overwrite existing file contents (no duplicate)
        service.files().update(
            fileId=existing_id,
            media_body=media,
            supportsAllDrives=True
        ).execute()
        return "updated"

    if existing_id and not overwrite:
        # Already there; don't duplicate
        return "skipped"

    # Doesn't exist yet -> create it
    meta = {"name": local_path.name, "parents": [parent_id]}
    service.files().create(
        body=meta,
        media_body=media,
        fields="id",
        supportsAllDrives=True
    ).execute()
    return "created"

def upload_tree(service, local_dir: Path, drive_parent_id: str, pbar: tqdm, stats: dict):
    for entry in sorted(local_dir.iterdir()):
        if entry.is_dir():
            child_id = ensure_drive_folder(service, entry.name, drive_parent_id)
            upload_tree(service, entry, child_id, pbar, stats)
        else:
            overwrite = entry.suffix.lower() == ".csv"
            result = upload_file(service, entry, drive_parent_id, overwrite=overwrite)

            if result == "created":
                stats["created"] += 1
            elif result == "updated":
                stats["updated"] += 1
            elif result == "skipped":
                stats["skipped"] += 1

            pbar.update(1)
            pbar.set_postfix_str(f"{result}: {entry.name[:40]}", refresh=False)


def main():
    # Optional argument: YYYY-MM-DD (defaults to today)
    date_str = sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y-%m-%d")

    stats = {
        "created": 0,
        "updated": 0,
        "skipped": 0,
    }


    print(f"[INFO] Using LOCAL_BASE_DATA_DIR: {LOCAL_BASE_DATA_DIR}")
    print(f"[INFO] Target date folder: {date_str}")

    local_day_dir = Path(LOCAL_BASE_DATA_DIR) / date_str
    if not local_day_dir.exists() or not local_day_dir.is_dir():
        print(f"[INFO] Available day folders in {LOCAL_BASE_DATA_DIR}:")
        try:
            base = Path(LOCAL_BASE_DATA_DIR)
            if base.exists() and base.is_dir():
                found_any = False
                for p in sorted(base.iterdir()):
                    if p.is_dir():
                        print("  -", p.name)
                        found_any = True
                if not found_any:
                    print("  (No subfolders found.)")
            else:
                print("  (Base directory does not exist or is not a directory.)")
        except Exception as e:
            print("  (Could not list folders:", e, ")")

        print(f"ERROR: Day folder not found: {local_day_dir}")
        sys.exit(1)

    service = get_drive_service()

    # Create/find the dated folder in Drive under your parent folder
    drive_day_id = ensure_drive_folder(service, date_str, DRIVE_PARENT_FOLDER_ID)

    # Upload everything inside the local dated folder (CSV + photos/)
    total_files = count_files_recursive(local_day_dir)
    print(f"[INFO] Uploading {total_files} files from: {local_day_dir}")

    with tqdm(total=total_files, unit="file", desc="Uploading", dynamic_ncols=True) as pbar:
        upload_tree(service, local_day_dir, drive_day_id, pbar, stats)

    print(f"Uploaded: {local_day_dir} -> Drive folder '{date_str}'")
    print("\nUpload Summary")
    print(f"  Created: {stats['created']}")
    print(f"  Updated: {stats['updated']}")
    print(f"  Skipped: {stats['skipped']}")


def pause_to_close(message="\nDone. Press Enter to close this window..."):
    # Only pause if we are attached to a real terminal
    if not sys.stdin.isatty():
        return
    try:
        input(message)
    except EOFError:
        pass

if __name__ == "__main__":
    exit_code = 0
    try:
        main()
        print("\n✅ Upload complete.")
    except KeyboardInterrupt:
        exit_code = 130
        print("\n⚠️ Upload cancelled.")
    except Exception as e:
        exit_code = 1
        print(f"\n❌ Upload failed: {e}")
    finally:
        pause_to_close("\nPress Enter to close this window...")
    sys.exit(exit_code)

