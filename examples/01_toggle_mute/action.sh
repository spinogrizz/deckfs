#!/bin/bash

# Toggle system audio mute state
# Image change will be handled automatically by background.sh monitoring

MUTED=$(pactl get-sink-mute @DEFAULT_SINK@ | grep -o "yes\|no")

if [ "$MUTED" = "yes" ]; then
    pactl set-sink-mute @DEFAULT_SINK@ 0
else
    pactl set-sink-mute @DEFAULT_SINK@ 1
fi

