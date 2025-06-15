#!/bin/bash

# Update image based on light state
# Usage: bash update.sh [on|off]
# Default: off

STATE=${1:-off}

if [ "$STATE" = "on" ]; then
    ln -sf light_on.png image.png
else
    ln -sf light_off.png image.png
fi