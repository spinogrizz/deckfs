#!/bin/bash

# Home Assistant Light Status Monitor
# 
# Required environment variables in ~/.local/streamdeck/env.local:
# HOME_ASSISTANT_KEY="Bearer your_long_lived_access_token_here"
# HOME_ASSISTANT_URL="http://10.42.20.1:8123"

# Read entity ID from file
ENTITY_ID=$(cat entity.txt)

# Status check API URL
API_URL="${HOME_ASSISTANT_URL}/api/states/${ENTITY_ID}"

# Store previous state to avoid unnecessary updates
PREVIOUS_STATE=""

while true; do
    # Get current light state
    RESPONSE=$(curl -s -H "Authorization: ${HOME_ASSISTANT_KEY}" "${API_URL}")
    
    if [ $? -eq 0 ] && [ -n "$RESPONSE" ]; then
        # Extract state for our specific entity (take first match only)
        CURRENT_STATE=$(echo "$RESPONSE" | grep -o '"state":"[^"]*"' | head -1 | cut -d'"' -f4)
        
        # Update image only if state changed
        if [ "$CURRENT_STATE" != "$PREVIOUS_STATE" ]; then
            bash update.sh "$CURRENT_STATE"
            PREVIOUS_STATE="$CURRENT_STATE"
        fi
    fi
    
    sleep 5
done