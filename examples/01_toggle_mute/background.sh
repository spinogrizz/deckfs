#!/bin/bash

# Background script - monitors system mute state changes
# This script runs continuously in background and calls update.sh when mute state changes

# Monitor PulseAudio events for sink mute changes
pactl subscribe | grep --line-buffered "Event 'change' on sink" | while read -r line; do
    echo "$(date): Detected audio sink change"
    bash update.sh
done