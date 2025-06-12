#!/bin/bash

# Background script - monitors system mute state changes
# This script runs continuously in background and calls update.sh when mute state changes

PREV_MUTED=""

# Monitor PulseAudio events for sink mute changes
pactl subscribe | grep --line-buffered "Event 'change' on sink" | while read -r line; do
    echo "$(date): Detected audio sink change"

    CURRENT_MUTED=$(pactl get-sink-mute @DEFAULT_SINK@ | grep -o "yes\|no" 2>/dev/null)
    
    if [ "$CURRENT_MUTED" != "$PREV_MUTED" ]; then
        bash update.sh
        PREV_MUTED="$CURRENT_MUTED"
    fi
done