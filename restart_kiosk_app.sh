#!/bin/bash
# Restart the sign-in kiosk app in the running desktop session, e.g. over SSH
# after a code or settings change. Reuses the display settings of the running
# app (or the desktop defaults if it isn't running). Output: /tmp/kiosk_gui.log
P=$(pgrep -f "python kiosk_gui\.py$" | head -1)
[ -n "$P" ] && ENVS=$(tr "\0" "\n" </proc/$P/environ | grep -E "^(WAYLAND_DISPLAY|DISPLAY|XDG_RUNTIME_DIR|DBUS_SESSION_BUS_ADDRESS|QT_[A-Z_]*|WLR_XWAYLAND)=")
[ -z "$ENVS" ] && ENVS="WAYLAND_DISPLAY=wayland-0 DISPLAY=:0 XDG_RUNTIME_DIR=/run/user/1000 DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus QT_WAYLAND_DISABLE_WINDOWDECORATION=1 QT_QPA_PLATFORMTHEME=qt5ct"
[ -n "$P" ] && kill $P && while kill -0 $P 2>/dev/null; do sleep 0.5; done
cd /home/gnomeskillet/signin_kiosk
env $ENVS setsid nohup /home/gnomeskillet/kiosk-env/bin/python kiosk_gui.py > /tmp/kiosk_gui.log 2>&1 < /dev/null &
