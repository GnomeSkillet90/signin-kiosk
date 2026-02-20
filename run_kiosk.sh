#!/bin/bash
cd /home/gnomeskillet/signin_kiosk

source /home/gnomeskillet/kiosk-env/bin/activate
export DISPLAY=:0

python kiosk_gui.py