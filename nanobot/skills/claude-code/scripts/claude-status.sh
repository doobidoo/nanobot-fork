#!/bin/bash
# Check Claude Code tmux session status
# Returns: running, busy, stopped

SESSION="claude"

# Check if session exists
if ! tmux has-session -t "$SESSION" 2>/dev/null; then
    echo "stopped"
    exit 0
fi

# Check if Claude is ready (empty prompt line)
OUTPUT=$(tmux capture-pane -t "$SESSION" -p -S -10 2>/dev/null)

if echo "$OUTPUT" | grep -q "^❯ *$"; then
    echo "running"
elif echo "$OUTPUT" | grep -q "^❯"; then
    # Has prompt but with text = busy typing or waiting
    echo "busy"
else
    # No prompt visible = processing
    echo "busy"
fi
