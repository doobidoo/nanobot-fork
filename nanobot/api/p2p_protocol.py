"""
P2P Protocol with Safeguards
Prevents infinite loops between ARGUS and Nanobot
"""

import json
import time
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional
from dataclasses import dataclass, asdict

# Safeguard constants
MAX_TURNS_PER_CONVERSATION = 3
COOLDOWN_SECONDS = 60
CONVERSATION_TIMEOUT_MINUTES = 5
DONE_SIGNALS = ["DONE", "END", "FERTIG", "ABGESCHLOSSEN"]

# State file
STATE_FILE = Path.home() / ".local/share/p2p-state.json"


@dataclass
class Conversation:
    id: str
    started_at: str
    turns: int = 0
    last_message_at: str = ""
    completed: bool = False


def load_state() -> dict:
    """Load P2P state from file."""
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except:
            pass
    return {"conversations": {}, "last_response_at": None}


def save_state(state: dict):
    """Save P2P state to file."""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))


def check_safeguards(conversation_id: str, source: str) -> tuple[bool, str]:
    """
    Check if we should respond to this message.
    Returns (should_respond, reason)
    """
    state = load_state()
    now = datetime.now()

    # 1. Global cooldown - don't respond too quickly
    if state.get("last_response_at"):
        last = datetime.fromisoformat(state["last_response_at"])
        if (now - last).total_seconds() < COOLDOWN_SECONDS:
            return False, f"Cooldown active ({COOLDOWN_SECONDS}s)"

    # 2. Check conversation limits
    conv = state["conversations"].get(conversation_id)
    if conv:
        # Check if already completed
        if conv.get("completed"):
            return False, "Conversation already completed"

        # Check turn limit
        if conv.get("turns", 0) >= MAX_TURNS_PER_CONVERSATION:
            return False, f"Max turns reached ({MAX_TURNS_PER_CONVERSATION})"

        # Check timeout
        started = datetime.fromisoformat(conv["started_at"])
        if (now - started).total_seconds() > CONVERSATION_TIMEOUT_MINUTES * 60:
            return False, "Conversation timed out"

    # 3. Don't respond to ourselves
    if source == "nanobot":
        return False, "Won't respond to own messages"

    return True, "OK"


def start_conversation(conversation_id: str, source: str) -> dict:
    """Start or continue a conversation."""
    state = load_state()
    now = datetime.now().isoformat()

    if conversation_id not in state["conversations"]:
        state["conversations"][conversation_id] = {
            "id": conversation_id,
            "started_at": now,
            "turns": 0,
            "last_message_at": now,
            "completed": False,
            "source": source
        }

    return state


def record_turn(conversation_id: str):
    """Record a turn in the conversation."""
    state = load_state()
    now = datetime.now().isoformat()

    if conversation_id in state["conversations"]:
        state["conversations"][conversation_id]["turns"] += 1
        state["conversations"][conversation_id]["last_message_at"] = now

    state["last_response_at"] = now
    save_state(state)


def end_conversation(conversation_id: str, reason: str = "completed"):
    """Mark conversation as completed."""
    state = load_state()

    if conversation_id in state["conversations"]:
        state["conversations"][conversation_id]["completed"] = True
        state["conversations"][conversation_id]["end_reason"] = reason

    save_state(state)


def check_done_signal(message: str) -> bool:
    """Check if message contains a DONE signal."""
    upper = message.upper()
    return any(signal in upper for signal in DONE_SIGNALS)


def cleanup_old_conversations(max_age_hours: int = 24):
    """Remove conversations older than max_age_hours."""
    state = load_state()
    now = datetime.now()
    cutoff = now - timedelta(hours=max_age_hours)

    to_remove = []
    for conv_id, conv in state["conversations"].items():
        started = datetime.fromisoformat(conv["started_at"])
        if started < cutoff:
            to_remove.append(conv_id)

    for conv_id in to_remove:
        del state["conversations"][conv_id]

    save_state(state)
    return len(to_remove)
