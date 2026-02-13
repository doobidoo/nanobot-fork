---
name: claude-code
description: Send prompts to Claude Code running in a tmux session and get responses.
metadata: {"nanobot":{"emoji":"🤖","os":["linux"],"requires":{"bins":["tmux"]}}}
---

# Claude Code Skill

Interact with Claude Code (Anthropic's CLI) running in a persistent tmux session.

## Prerequisites

The Claude Code tmux session must be running:

```bash
systemctl --user start claude-tmux
```

Or manually:

```bash
~/.local/bin/claude-tmux-start.sh
```

## Sending Prompts

Use the helper script to send a prompt and capture the response:

```bash
{baseDir}/scripts/ask-claude.sh "Your prompt here"
```

Or manually via tmux:

```bash
# Send prompt
tmux send-keys -t claude 'Your prompt here' Enter

# Wait for response (check for prompt symbol)
sleep 10

# Capture output
tmux capture-pane -t claude -p -S -100
```

## Checking Status

```bash
{baseDir}/scripts/claude-status.sh
```

Returns:
- `running` - Claude Code is ready for prompts
- `busy` - Claude is processing a request
- `stopped` - Session not running

## Session Management

```bash
# Start session
systemctl --user start claude-tmux

# Stop session
systemctl --user stop claude-tmux

# Restart session
systemctl --user restart claude-tmux

# Attach to session (interactive)
tmux attach -t claude
# Detach with Ctrl+B, then D
```

## Output Parsing

Claude Code output includes:
- `❯` - Input prompt (ready for new input)
- `●` - Claude's response text
- `⏵⏵` - Status line (bypass permissions indicator)

To extract just the response:

```bash
{baseDir}/scripts/ask-claude.sh "prompt" | grep "^●" | sed 's/^● //'
```

## Example Usage

```bash
# Simple question
{baseDir}/scripts/ask-claude.sh "What is 2+2?"

# Code generation
{baseDir}/scripts/ask-claude.sh "Write a Python function to reverse a string"

# File operations (Claude has access to filesystem)
{baseDir}/scripts/ask-claude.sh "Read and summarize ~/notes.txt"
```

## Tips

- Keep prompts concise for faster responses
- Claude Code has full filesystem access in bypass permissions mode
- For long operations, increase the wait timeout
- Check `~/.local/share/claude-tmux.log` for session logs
