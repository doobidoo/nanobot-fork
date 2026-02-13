"""
ARGUS Client for Nanobot
Enables Nanobot to initiate conversations with ARGUS (bidirectional P2P)
"""

import json
import logging
import requests
from datetime import datetime
from typing import Optional
from pathlib import Path

logger = logging.getLogger("p2p")

# ARGUS Configuration
ARGUS_URL = "http://127.0.0.1:3200"
ARGUS_TIMEOUT = 30

# Log file for outgoing messages
LOG_FILE = Path.home() / ".local/share/nanobot-p2p.log"


def log_outgoing(message: str, response: str = None):
    """Log outgoing messages to ARGUS."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if response:
        log_line = f"{timestamp} | OUT | nanobot → argus | Q: {message[:80]}... | A: {response[:80]}..."
    else:
        log_line = f"{timestamp} | OUT | nanobot → argus | {message[:150]}"

    logger.info(log_line)

    try:
        with open(LOG_FILE, "a") as f:
            f.write(log_line + "\n")
    except Exception:
        pass


def check_argus() -> bool:
    """Check if ARGUS is online."""
    try:
        r = requests.get(f"{ARGUS_URL}/health", timeout=5)
        return r.status_code == 200
    except Exception:
        return False


def send_to_argus(message: str, source: str = "nanobot") -> dict:
    """
    Send a message to ARGUS.

    Args:
        message: The message text to send
        source: Identifier for the sender (default: nanobot)

    Returns:
        dict with status, message (response), timestamp
    """
    if not check_argus():
        log_outgoing(message, "ERROR: ARGUS offline")
        return {
            "success": False,
            "error": "ARGUS is offline",
            "message": None
        }

    try:
        payload = {
            "from": source,
            "text": message
        }

        r = requests.post(
            f"{ARGUS_URL}/message",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=ARGUS_TIMEOUT
        )

        if r.status_code == 200:
            data = r.json()
            log_outgoing(message, data.get("message", ""))
            return {
                "success": True,
                "message": data.get("message"),
                "context": data.get("context", []),
                "timestamp": data.get("timestamp")
            }
        else:
            log_outgoing(message, f"ERROR: HTTP {r.status_code}")
            return {
                "success": False,
                "error": f"HTTP {r.status_code}",
                "message": None
            }

    except requests.exceptions.Timeout:
        log_outgoing(message, "ERROR: Timeout")
        return {
            "success": False,
            "error": "Request timed out",
            "message": None
        }
    except Exception as e:
        log_outgoing(message, f"ERROR: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "message": None
        }


def notify_argus(title: str, body: str, priority: str = "normal") -> dict:
    """
    Send a notification to ARGUS.

    Args:
        title: Notification title
        body: Notification body
        priority: "normal", "high", or "critical"

    Returns:
        Response dict
    """
    emoji = {
        "normal": "ℹ️",
        "high": "⚠️",
        "critical": "🚨"
    }.get(priority, "ℹ️")

    message = f"{emoji} **{title}**\n\n{body}"
    return send_to_argus(message, source="nanobot-notify")


def ask_argus(question: str) -> Optional[str]:
    """
    Ask ARGUS a question and get response.

    Args:
        question: The question to ask

    Returns:
        ARGUS response text or None if failed
    """
    result = send_to_argus(f"❓ {question}", source="nanobot-ask")
    if result["success"]:
        return result["message"]
    return None


def report_to_argus(report_type: str, content: str) -> dict:
    """
    Send a report to ARGUS.

    Args:
        report_type: Type of report (e.g., "github", "digest", "discovery")
        content: Report content

    Returns:
        Response dict
    """
    emoji = {
        "github": "📊",
        "digest": "📋",
        "discovery": "🔍",
        "error": "❌",
        "success": "✅"
    }.get(report_type, "📝")

    message = f"{emoji} **{report_type.upper()} Report**\n\n{content}"
    return send_to_argus(message, source=f"nanobot-{report_type}")


# ============================================
# Proactive Triggers
# ============================================

def on_github_watch_complete(repo: str, report: str, has_new_issues: bool = False):
    """
    Called when GitHub watch completes - notify ARGUS proactively.
    """
    if has_new_issues:
        # High priority - new issues found
        notify_argus(
            title=f"Neue Issues in {repo}",
            body=report,
            priority="high"
        )
    else:
        # Normal report
        report_to_argus("github", f"**{repo}**\n{report}")


def on_discovery(what: str, details: str):
    """
    Called when Nanobot discovers something interesting.
    """
    notify_argus(
        title=f"Entdeckung: {what}",
        body=details,
        priority="normal"
    )


def on_error(context: str, error: str):
    """
    Called when an error occurs that ARGUS should know about.
    """
    notify_argus(
        title=f"Fehler: {context}",
        body=error,
        priority="high"
    )


def on_task_complete(task: str, result: str):
    """
    Called when a scheduled task completes.
    """
    report_to_argus("success", f"**{task}**\n\n{result}")
