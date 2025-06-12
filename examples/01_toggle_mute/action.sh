#!/bin/bash

# Toggle system audio mute state and update button image accordingly
# This script toggles mute state and calls update.sh to refresh the button image

# Get current mute state (0 = not muted, 1 = muted)
MUTED=$(pactl get-sink-mute @DEFAULT_SINK@ | grep -o "yes\|no")

if [ "$MUTED" = "yes" ]; then
    pactl set-sink-mute @DEFAULT_SINK@ 0
else
    pactl set-sink-mute @DEFAULT_SINK@ 1
fi

# Update image script will be called by background.sh