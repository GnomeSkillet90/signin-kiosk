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

## UPLOADING ATTENDANCE

From the kiosk:
    upload

This starts the upload in the background and shows live progress.

From terminal:
    python upload_kiosk_day.py
    (Optional: pass a specific date as YYYY-MM-DD)

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
  README.txt
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
