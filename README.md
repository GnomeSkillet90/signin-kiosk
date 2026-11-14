# SIGN-IN KIOSK

A Raspberry Pi–based sign-in kiosk system used for student attendance and verification.
Designed for real-world use (Saturday School), with camera photo capture, barcode support,
and Google Drive uploads. 

----------------------------------------------------------------

## WHO THIS IS FOR

This project is intended for educators or administrators 
comfortable with basic Raspberry Pi and Python setup.

----------------------------------------------------------------

## OVERVIEW

This project consists of **two Python programs**:

1. **kiosk_gui.py**
   - Full-screen PyQt5 kiosk application used by students to sign in

2. **upload_kiosk_day.py**
   - Separate uploader that sends the day’s attendance data to Google Drive

The system was deployed and successfully used in a live school environment.

----------------------------------------------------------------

## KIOSK FEATURES (kiosk_gui.py)

- Full-screen touchscreen-friendly GUI (PyQt5)
- Multiple sign-in methods:
  • Numeric Student ID
  • Chromebook barcode (username portion)
  • Full email address (domain stripped automatically)
- Case-insensitive, flexible input handling
- Confirmation dialog before sign-in
  • Informs students that a photo will be taken for verification
- Photo capture using **Picamera2**
- Automatic daily logging to CSV
- Photos and CSV stored together in a dated folder:

    signin_kiosk_data/
      YYYY-MM-DD/
        signins_YYYY-MM-DD.csv
        photos/
          Last_First_HHMM_ID.jpg

- Live on-screen counter showing number of students signed in
- Prevents duplicate sign-ins
- Clear status messages with auto-reset
- Hidden admin command:
  • Typing `upload` triggers the upload process **without closing the kiosk**
- Runs automatically on boot via desktop autostart

----------------------------------------------------------------

## UPLOAD FEATURES (upload_kiosk_day.py)

- Uploads the current day’s folder (CSV + photos) to Google Drive
- Uses a Google Drive **service account**
- Automatically selects storage location:
  • USB drive if present
  • Falls back to SD card
- Safe re-runs:
  • Photos are skipped if already uploaded
  • CSV is updated / overwritten to support late arrivals
- Displays progress using `tqdm`
- Can be run:
  • Manually from a terminal
  • Via desktop shortcut
  • Triggered from inside the kiosk GUI
- When triggered from the kiosk:
  • Runs in the background
  • Shows live upload output in a GUI dialog
  • Does not block or freeze the kiosk

----------------------------------------------------------------

## DESIGN GOALS

- Reliable in real-world use
- No data loss
- No duplicate uploads
- Responsive UI even during long uploads
- Safe handling of student data
- Minimal maintenance once deployed

----------------------------------------------------------------

## SECURITY & PRIVACY

The repository **does NOT include**:
- Student CSV data
- Photos
- Google service account credentials
- Virtual environments

These are excluded via `.gitignore`.

----------------------------------------------------------------

## RUNNING THE KIOSK

Activate environment:
    source kiosk-env/bin/activate

Start kiosk manually:
    python kiosk_gui.py

The kiosk is configured to start automatically on boot via desktop autostart.

----------------------------------------------------------------

## PER-KIOSK SETTINGS

Each kiosk keeps its own settings in `~/.config/kiosk/` (outside the
repo, so restoring from GitHub does not bring them back):

- `kiosk_name` – name used to tag this kiosk's rows in the shared
  Drive sign-in sheet (e.g. `kiosk1`, `kiosk2`). Must differ per kiosk.
- `settings.json` – optional hardware settings. Missing file = defaults.
  Start from the template, which holds the defaults, then edit it:
      cp ~/signin_kiosk/settings.example.json ~/.config/kiosk/settings.json
  Restart the app to apply changes (~/signin_kiosk/restart_kiosk_app.sh).
    camera_rotation_ccw: rotate preview and photos counterclockwise
                         by 0, 90, 180 or 270 degrees (default 0)
    rfid_enabled:        read student RFID tags (default true); set false
                         on a kiosk with no RFID reader attached
- `drive_sa.json` – Google Drive service account key. Restore from a
  private backup; NEVER commit it.

Current kiosks:

    kiosk1 (signin-kiosk):   kiosk_name = kiosk1
                             settings.json = defaults (copy of settings.example.json)
    kiosk2 (signin-kiosk2):  kiosk_name = kiosk2
                             settings.json = {"camera_rotation_ccw": 90,
                                              "rfid_enabled": false}

Note for Camera Module 3: the case must not press on the round black
lens barrel, or autofocus can't move the lens and every photo is blurry.

----------------------------------------------------------------

## UPLOADING ATTENDANCE

From the kiosk:
    upload

This starts the upload in the background and shows live progress.

From terminal:
    python upload_kiosk_day.py
    (Optional: pass a specific date as YYYY-MM-DD)

----------------------------------------------------------------

## MAINTENANCE TOOLS (over SSH)

Restart the sign-in app without rebooting (after a git pull or a
settings.json change). Log goes to /tmp/kiosk_gui.log:
    ~/signin_kiosk/restart_kiosk_app.sh

Remove a sign-in (e.g. a test one) from this kiosk and from Drive:
    ~/kiosk-env/bin/python ~/signin_kiosk/remove_signin.py 2026-11-14 123456789
The local row and photo are moved to ~/removed_signins/<date>/, the
row is removed from the shared and per-kiosk CSVs on Drive, and the
Drive photo is moved to the trash. Restart the app afterwards so the
student can sign in again. Rows already copied into the Google Sheet
must be deleted there by hand.

----------------------------------------------------------------

## REQUIREMENTS

- Raspberry Pi OS (X11 desktop)
- Python 3.9+
- PyQt5
- Picamera2
- Google Drive API (service account)
- Internet connection for uploads

----------------------------------------------------------------

## REPOSITORY STRUCTURE

signin_kiosk/
  kiosk_gui.py
  upload_kiosk_day.py
  restart_kiosk_app.sh
  remove_signin.py
  README.md
  .gitignore
  signin_kiosk_data/   (ignored; created at runtime)

----------------------------------------------------------------

## STATUS

✔ Deployed  
✔ Tested in production  
✔ Actively used  
✔ Version-controlled on GitHub  

----------------------------------------------------------------

## SETUP OVERVIEW (for new installs)

1. Install Raspberry Pi OS (desktop)
2. Enable camera support
3. Create Python virtual environment
4. Install requirements
5. Configure Google Drive service account
6. Update config paths as needed
7. Enable desktop autostart


----------------------------------------------------------------

## LICENSE

Internal / educational use.
Not intended for redistribution without modification.
