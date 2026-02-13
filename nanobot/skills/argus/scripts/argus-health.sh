#!/bin/bash
# Check ARGUS health status

ARGUS_URL="${ARGUS_URL:-http://127.0.0.1:3200}"

response=$(curl -s -o /dev/null -w "%{http_code}" "$ARGUS_URL/health" 2>/dev/null)

if [[ "$response" == "200" ]]; then
    echo "running"
else
    echo "stopped"
    exit 1
fi
