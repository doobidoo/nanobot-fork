# nanobot-fork

Heinrich's fork of [nanobot-ai](https://pypi.org/project/nanobot-ai/) with custom patches.

## Custom Patches

### Telegram Typing Indicator (2026-02-08)
- Shows "typing..." in Telegram while processing messages
- File: `nanobot/channels/telegram.py`

## Installation

```bash
cd ~/repositories/nanobot-fork
pip install -e .
```

## Usage

Same as upstream nanobot-ai:
```bash
nanobot gateway
```

## Updating from Upstream

1. Check latest version: `pip index versions nanobot-ai`
2. Download wheel: `pip download nanobot-ai --no-deps -d /tmp`
3. Extract and compare: `unzip /tmp/nanobot_ai-*.whl -d /tmp/upstream`
4. Merge changes manually, preserving custom patches
