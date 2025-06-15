#!/bin/bash

# Home Assistant Light Control
# 
# Required environment variables in ~/.local/streamdeck/env.local:
# HOME_ASSISTANT_KEY="Bearer your_long_lived_access_token_here"
# HOME_ASSISTANT_URL="http://10.42.20.1:8123"

# Read entity ID from file
ENTITY_ID=$(cat entity.txt)

# Toggle light via Home Assistant API
API_URL="${HOME_ASSISTANT_URL}/api/services/light/toggle"

# Toggle light and get response with new state
RESPONSE=$(curl -s -X POST \
  -H "Authorization: ${HOME_ASSISTANT_KEY}" \
  -H 'Content-Type: application/json' \
  -d "{\"entity_id\": \"${ENTITY_ID}\"}" \
  "${API_URL}")

if [ $? -eq 0 ] && [ -n "$RESPONSE" ]; then
    # Extract state from toggle response for our specific entity (take first match only)
    CURRENT_STATE=$(echo "$RESPONSE" | grep -o '"state":"[^"]*"' | head -1 | cut -d'"' -f4)
    
    # Update image via update.sh
    bash update.sh "$CURRENT_STATE"
fi