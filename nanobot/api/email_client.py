"""
Email Client for Nanobot
Send emails via Mutt (configured with Gmail)
"""

import subprocess
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("p2p")
LOG_FILE = Path.home() / ".local/share/nanobot-p2p.log"


def send_email(to: str, subject: str, body: str, from_name: str = "Nanobot") -> dict:
    """
    Send an email via Mutt.
    
    Args:
        to: Recipient email address
        subject: Email subject
        body: Email body text
        from_name: Sender name (default: Nanobot)
    
    Returns:
        dict with success status and message
    """
    try:
        # Add signature
        full_body = f"{body}\n\n--\nGesendet von {from_name} via Mutt"
        
        # Send via mutt
        process = subprocess.run(
            ["mutt", "-s", subject, to],
            input=full_body.encode(),
            capture_output=True,
            timeout=30
        )
        
        if process.returncode == 0:
            log_line = f"{datetime.now():%Y-%m-%d %H:%M:%S} | 📧 EMAIL | {to} | {subject}"
            logger.info(log_line)
            with open(LOG_FILE, "a") as f:
                f.write(log_line + "\n")
            
            return {
                "success": True,
                "message": f"Email sent to {to}",
                "subject": subject
            }
        else:
            error = process.stderr.decode()
            return {
                "success": False,
                "error": error
            }
            
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Timeout sending email"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def notify_by_email(subject: str, body: str, to: str = "henry.krupp@gmail.com") -> dict:
    """
    Send a notification email (default: to owner).
    """
    return send_email(to, f"[Nanobot] {subject}", body)
