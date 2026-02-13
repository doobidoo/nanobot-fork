#!/bin/bash
# Ask Claude Code a question and get the response
# Usage: ask-claude.sh "Your prompt" [TIMEOUT_SECONDS]

set -e

SESSION="claude"
PROMPT="$1"
TIMEOUT="${2:-60}"

if [[ -z "$PROMPT" ]]; then
    echo "Usage: $0 \"prompt\" [timeout_seconds]"
    exit 1
fi

# Check if session exists
if ! tmux has-session -t "$SESSION" 2>/dev/null; then
    echo "Error: Claude tmux session not running"
    echo "Start with: systemctl --user start claude-tmux"
    exit 1
fi

# Send the prompt (split into text + Enter for reliability)
tmux send-keys -t "$SESSION" -l "$PROMPT"
sleep 0.3
tmux send-keys -t "$SESSION" Enter

# Wait for response with timeout
ELAPSED=0
STABLE_COUNT=0

while [[ $ELAPSED -lt $TIMEOUT ]]; do
    sleep 2
    ELAPSED=$((ELAPSED + 2))

    # Check current output
    CURRENT=$(tmux capture-pane -t "$SESSION" -p)

    # Check if Claude is done (prompt symbol appeared and lines stable)
    if echo "$CURRENT" | tail -5 | grep -q "^❯ *$"; then
        # Prompt is empty = ready for input
        STABLE_COUNT=$((STABLE_COUNT + 1))
        if [[ $STABLE_COUNT -ge 2 ]]; then
            break
        fi
    else
        STABLE_COUNT=0
    fi
done

# Capture output
OUTPUT=$(tmux capture-pane -t "$SESSION" -p -S -100)

# Extract the LAST response block (everything between the second-to-last ❯ and the final ❯)
# This captures all ● lines and their indented content
echo "$OUTPUT" | awk '
    /^❯/ {
        # Save current block as previous, start new block
        prev_block = curr_block
        curr_block = ""
        next
    }
    /^●/ || /^  / {
        # Accumulate response content (● lines and indented continuation)
        curr_block = curr_block $0 "\n"
    }
    END {
        # Print the previous block (the completed response before the final empty ❯)
        print prev_block
    }
' | grep -v "^$" | head -30
