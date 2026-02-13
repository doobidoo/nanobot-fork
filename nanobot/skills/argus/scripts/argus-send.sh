#!/bin/bash
# Send a message to ARGUS
# Usage: argus-send.sh "message"

ARGUS_URL="${ARGUS_URL:-http://127.0.0.1:3200}"
LOG_FILE="${HOME}/.local/share/nanobot-p2p.log"
MESSAGE="$1"

if [[ -z "$MESSAGE" ]]; then
    echo "Usage: $0 \"message\""
    exit 1
fi

TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

# Log the outgoing message
echo "[$TIMESTAMP] NANOBOT → ARGUS: $MESSAGE" >> "$LOG_FILE"

# Send to ARGUS
response=$(curl -s -X POST "$ARGUS_URL/api/message" \
    -H "Content-Type: application/json" \
    -d "{\"message\": \"$MESSAGE\", \"source\": \"nanobot\"}" 2>/dev/null)

# Log the response
echo "[$TIMESTAMP] ARGUS → NANOBOT: $response" >> "$LOG_FILE"

echo "$response"
