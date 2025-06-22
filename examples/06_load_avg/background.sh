#!/bin/bash

# Background script to refresh load average display every 10 seconds
# This touches the draw.py file to trigger filesystem events and redraw

SCRIPT_DIR="$(dirname "$0")"

while true; do
    sleep 10
    
    # Touch the draw script to trigger a file change event
    # This will cause the daemon to detect the change and redraw the button
    touch "$SCRIPT_DIR/draw.py"
done