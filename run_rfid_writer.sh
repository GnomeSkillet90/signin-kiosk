#!/bin/bash
set -e

cd /home/gnomeskillet/signin_kiosk

# Use the virtual environment (mfrc522 is installed here)
source /home/gnomeskillet/rfid-env/bin/activate

# Tell Tkinter to draw on the Pi’s attached display
export DISPLAY=:0

# Launch the GUI
python /home/gnomeskillet/signin_kiosk/rfid_writer_gui.py
