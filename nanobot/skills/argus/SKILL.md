---
name: argus
description: Communicate with ARGUS (24/7 monitoring assistant) via its HTTP API.
metadata: {"nanobot":{"emoji":"👁️","os":["linux"],"requires":{"bins":["curl"]}}}
---

# ARGUS Skill

Send messages and queries to ARGUS, the 24/7 monitoring assistant.

## Prerequisites

ARGUS relay must be running:
```bash
docker ps | grep argus
```

## Endpoints

ARGUS API runs on `http://127.0.0.1:3200`

### Health Check
```bash
{baseDir}/scripts/argus-health.sh
```

### Send Message
```bash
{baseDir}/scripts/argus-send.sh "Your message here"
```

## Example Usage

```bash
# Check if ARGUS is running
{baseDir}/scripts/argus-health.sh

# Send a message to ARGUS
{baseDir}/scripts/argus-send.sh "Check my calendar for today"

# Request a status update
{baseDir}/scripts/argus-send.sh "Give me a status update"
```

## P2P Communication

ARGUS can also call Nanobot via `http://127.0.0.1:8888/ask`

All interactions are logged to:
- Nanobot: `~/.local/share/nanobot-p2p.log`
- Shodh Memory (tag: p2p-exchange)
