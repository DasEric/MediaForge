#!/bin/sh
set -e

# Sensible locale / timezone defaults so Chromium does not look like a bare
# UTC server (Turnstile reads these).  Overridable from the environment.
export TZ="${TZ:-Europe/Berlin}"
export LANG="${LANG:-de_DE.UTF-8}"
export LANGUAGE="${LANGUAGE:-de_DE:de}"

# Start a session D-Bus so Chromium finds the services it expects; missing
# D-Bus is a small "automated container" signal.
if command -v dbus-launch >/dev/null 2>&1; then
    echo "[MediaForge] Starting D-Bus..."
    eval "$(dbus-launch --sh-syntax)" 2>/dev/null || true
fi

echo "[MediaForge] Starting virtual display (Xvfb)..."
Xvfb :99 -screen 0 1920x1080x24 -nolisten tcp &

echo "[MediaForge] Waiting for display to be ready..."
i=0
until xdpyinfo -display :99 >/dev/null 2>&1; do
    sleep 0.2
    i=$((i + 1))
    if [ $((i % 15)) -eq 0 ]; then
        echo "[MediaForge] Still waiting for Xvfb... (${i} attempts)"
    fi
done
echo "[MediaForge] Display ready."

echo "[MediaForge] Starting MediaForge..."
exec mediaforge -wP 8080 -wN -wH 0.0.0.0
