"""Remove one student_id's sign-in for a date from this kiosk's local data and from Drive.

Use it to clear test sign-ins (e.g. Test Student, 123456789).

Usage: ~/kiosk-env/bin/python ~/signin_kiosk/remove_signin.py DATE STUDENT_ID
Local CSV row and photo are moved to ~/removed_signins/DATE/, not deleted.
On Drive: the row is removed from the shared CSV and this kiosk's backup CSV,
and the photo is moved to the trash.
"""
import csv
import io
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import upload_kiosk_day as u  # noqa: E402

if len(sys.argv) != 3:
    sys.exit(__doc__)
date, sid = sys.argv[1], sys.argv[2]
kiosk = u.get_kiosk_name()
day_dir = os.path.join(u.LOCAL_BASE_DATA_DIR, date)
local_csv = os.path.join(day_dir, f"signins_{date}.csv")
backup_dir = os.path.expanduser(f"~/removed_signins/{date}")
os.makedirs(backup_dir, exist_ok=True)


def without(text):
    reader = csv.DictReader(io.StringIO(text))
    rows = list(reader)
    keep = [r for r in rows if (r.get("student_id") or "").strip() != sid]
    gone = [r for r in rows if (r.get("student_id") or "").strip() == sid]
    out = io.StringIO()
    w = csv.DictWriter(out, fieldnames=reader.fieldnames)
    w.writeheader()
    w.writerows(keep)
    return out.getvalue(), gone


# Local
text = open(local_csv, encoding="utf-8").read()
new_text, gone = without(text)
photos = {r.get("photo_filename", "") for r in gone if r.get("photo_filename")}
if gone:
    shutil.copy2(local_csv, os.path.join(backup_dir, os.path.basename(local_csv) + ".before"))
    open(local_csv, "w", encoding="utf-8", newline="").write(new_text)
    for p in photos:
        src = os.path.join(day_dir, "photos", p)
        if os.path.exists(src):
            shutil.move(src, os.path.join(backup_dir, p))
print(f"local: removed {len(gone)} row(s), moved {len(photos)} photo(s) to {backup_dir}")

# Drive
s = u.get_drive_service()
day_id, _ = u.find_child_by_name(s, u.DRIVE_PARENT_FOLDER_ID, date)
if not day_id:
    sys.exit("drive: no day folder")
for name in (f"signins_{date}.csv", f"signins_{date}_{kiosk}.csv"):
    fid, _ = u.find_child_by_name(s, day_id, name)
    if not fid:
        print(f"drive: {name} not found")
        continue
    t = s.files().get_media(fileId=fid, supportsAllDrives=True).execute().decode("utf-8-sig")
    nt, g = without(t)
    if g:
        u.put_csv_text(s, day_id, name, nt)
        photos |= {r.get("photo_filename", "") for r in g if r.get("photo_filename")}
    print(f"drive: {name}: removed {len(g)} row(s)")
photos_id, _ = u.find_child_by_name(s, day_id, "photos")
for p in photos:
    fid, _ = u.find_child_by_name(s, photos_id, p) if photos_id else (None, None)
    if fid:
        s.files().update(fileId=fid, body={"trashed": True}, supportsAllDrives=True).execute()
        print(f"drive: trashed photo {p}")
