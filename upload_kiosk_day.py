#!/usr/bin/env python3
import sys
import mimetypes
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
import os
import getpass
import csv
import io
import re
import socket

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseUpload
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

# Optional file holding this kiosk's name (e.g. "kiosk2"). Each kiosk needs a
# different name; without the file the Pi's hostname is used.
KIOSK_NAME_FILE = "/home/gnomeskillet/.config/kiosk/kiosk_name"

# ==================

SCOPES = ["https://www.googleapis.com/auth/drive"]
KIOSK_TZ = ZoneInfo("America/Chicago")


def now_local() -> datetime:
    return datetime.now(KIOSK_TZ)


def get_kiosk_name() -> str:
    name = os.environ.get("KIOSK_NAME", "").strip()
    if not name:
        try:
            with open(KIOSK_NAME_FILE, encoding="utf-8") as f:
                name = f.read().strip()
        except OSError:
            name = ""
    if not name:
        name = socket.gethostname()
    return re.sub(r"[^A-Za-z0-9_-]", "", name) or "kiosk"


def find_child_by_name(service, parent_id: str, name: str):
    """
    Return (file_id, mimeType) of an item named `name` directly under `parent_id`,
    or (None, None) if not found. If duplicates exist, the oldest one is used,
    so every kiosk picks the same item.
    """
    q = f"'{parent_id}' in parents and name='{name}' and trashed=false"
    res = service.files().list(
        q=q,
        fields="files(id,name,mimeType)",
        orderBy="createdTime",
        pageSize=10,
        supportsAllDrives=True,
        includeItemsFromAllDrives=True
    ).execute()
    files = res.get("files", [])
    if not files:
        return None, None
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
        orderBy="createdTime",
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

def put_csv_text(service, parent_id: str, name: str, text: str) -> str:
    """Create or overwrite a CSV named `name` under `parent_id` with `text`."""
    media = MediaIoBaseUpload(io.BytesIO(text.encode("utf-8")), mimetype="text/csv", resumable=False)
    existing_id, _ = find_child_by_name(service, parent_id, name)
    if existing_id:
        service.files().update(fileId=existing_id, media_body=media, supportsAllDrives=True).execute()
        return "updated"
    meta = {"name": name, "parents": [parent_id]}
    service.files().create(body=meta, media_body=media, fields="id", supportsAllDrives=True).execute()
    return "created"


def parse_csv_text(text: str):
    reader = csv.DictReader(io.StringIO(text), restval="")
    rows = []
    for row in reader:
        row.pop(None, None)  # drop overflow cells from malformed rows
        if any((v or "").strip() for v in row.values()):
            rows.append(row)
    return list(reader.fieldnames or []), rows


def merge_signins(drive_fields, drive_rows, local_fields, local_rows, kiosk_name):
    """
    Combine the shared Drive sign-in sheet with this kiosk's local one.
    - Rows already on Drive are kept; this kiosk's rows are tagged with its name.
    - One row per student_id: the earliest sign-in wins (a student who signed in
      at both kiosks keeps a single row, so the Sheet script finds one photo).
    Returns (fieldnames, rows, info).
    """
    for row in local_rows:
        row["kiosk"] = kiosk_name

    fields = []
    for name in list(local_fields) + list(drive_fields):
        if name and name != "kiosk" and name not in fields:
            fields.append(name)
    fields.append("kiosk")

    by_sid = {}
    no_sid = []
    no_sid_seen = set()
    # Students already on Drive from a *different* kiosk (blank = written by
    # the old single-kiosk uploader, i.e. not known to be another kiosk).
    other_kiosk_sids = {
        (r.get("student_id") or "").strip()
        for r in drive_rows
        if (r.get("kiosk") or "").strip() not in ("", kiosk_name)
    }
    drive_sids = {(r.get("student_id") or "").strip() for r in drive_rows}
    local_sids = {(r.get("student_id") or "").strip() for r in local_rows}
    added = len(local_sids - drive_sids - {""})
    both = (local_sids & other_kiosk_sids) - {""}

    for row in drive_rows + local_rows:
        sid = (row.get("student_id") or "").strip()
        if not sid:
            key = tuple((f, (row.get(f) or "").strip()) for f in fields if f != "kiosk")
            if key not in no_sid_seen:
                no_sid_seen.add(key)
                no_sid.append(row)
            continue
        current = by_sid.get(sid)
        if current is None or (row.get("timestamp") or "") < (current.get("timestamp") or ""):
            by_sid[sid] = row

    merged = sorted(list(by_sid.values()) + no_sid, key=lambda r: r.get("timestamp") or "")
    info = {"drive_before": len(drive_rows), "added": added, "total": len(merged), "both": len(both)}
    return fields, merged, info


def upload_shared_signins(service, local_csv: Path, drive_parent_id: str, kiosk_name: str) -> str:
    """Merge this kiosk's sign-ins into the shared Drive CSV (same name as the local file)."""
    local_text = local_csv.read_text(encoding="utf-8-sig")
    local_fields, local_rows = parse_csv_text(local_text)

    drive_fields, drive_rows = [], []
    existing_id, _ = find_child_by_name(service, drive_parent_id, local_csv.name)
    if existing_id:
        data = service.files().get_media(fileId=existing_id, supportsAllDrives=True).execute()
        drive_fields, drive_rows = parse_csv_text(data.decode("utf-8-sig"))

    fields, rows, info = merge_signins(drive_fields, drive_rows, local_fields, local_rows, kiosk_name)

    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=fields, extrasaction="ignore", restval="")
    writer.writeheader()
    writer.writerows(rows)
    result = put_csv_text(service, drive_parent_id, local_csv.name, out.getvalue())

    tqdm.write(
        f"[INFO] Shared sheet {local_csv.name}: {info['drive_before']} rows already on Drive, "
        f"{info['added']} new from {kiosk_name}, {info['total']} total."
    )
    if info["both"]:
        tqdm.write(f"[INFO] {info['both']} student(s) signed in at more than one kiosk; kept the earliest sign-in.")

    # Untouched copy of this kiosk's own sheet, as a backup. The Sheet script
    # only reads the exact shared name, so it ignores these.
    backup_name = f"{local_csv.stem}_{kiosk_name}{local_csv.suffix}"
    put_csv_text(service, drive_parent_id, backup_name, local_text)
    return result


def upload_tree(service, local_dir: Path, drive_parent_id: str, pbar: tqdm, stats: dict, kiosk_name: str = ""):
    for entry in sorted(local_dir.iterdir()):
        if entry.is_dir():
            child_id = ensure_drive_folder(service, entry.name, drive_parent_id)
            upload_tree(service, entry, child_id, pbar, stats, kiosk_name)
        else:
            if kiosk_name and entry.name.startswith("signins_") and entry.suffix.lower() == ".csv":
                result = upload_shared_signins(service, entry, drive_parent_id, kiosk_name)
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
    date_str = sys.argv[1] if len(sys.argv) > 1 else now_local().strftime("%Y-%m-%d")

    stats = {
        "created": 0,
        "updated": 0,
        "skipped": 0,
    }


    print(f"[INFO] Using LOCAL_BASE_DATA_DIR: {LOCAL_BASE_DATA_DIR}")
    print(f"[INFO] Target date folder: {date_str}")
    kiosk_name = get_kiosk_name()
    print(f"[INFO] Kiosk name: {kiosk_name}")

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
        upload_tree(service, local_day_dir, drive_day_id, pbar, stats, kiosk_name)

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
