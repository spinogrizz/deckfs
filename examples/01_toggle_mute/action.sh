#!/bin/bash

# Toggle system audio mute state and update button image accordingly
# This script checks the current mute state and toggles it using PulseAudio

# Get current mute state (0 = not muted, 1 = muted)
MUTED=$(pactl get-sink-mute @DEFAULT_SINK@ | grep -o "yes\|no")

if [ "$MUTED" = "yes" ]; then
    # Currently muted - unmute
    pactl set-sink-mute @DEFAULT_SINK@ 0
    # Switch to unmuted icon
    ln -sf unmuted.png image.png
    echo "Audio unmuted"
else
    # Currently unmuted - mute
    pactl set-sink-mute @DEFAULT_SINK@ 1
    # Switch to muted icon
    ln -sf muted.png image.png
    echo "Audio muted"
fi