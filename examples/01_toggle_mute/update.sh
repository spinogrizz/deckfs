#!/bin/bash

# Update script - synchronizes button image with current system mute state
# This script is called on daemon start and when update script is modified

# Get current mute state (0 = not muted, 1 = muted)
MUTED=$(pactl get-sink-mute @DEFAULT_SINK@ | grep -o "yes\|no")

# Show muted or unmuted icon, depending on the current state
if [ "$MUTED" = "yes" ]; then
    ln -sf muted.png image.png
else
    ln -sf unmuted.png image.png
fi