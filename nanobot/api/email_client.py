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


def send_email(to: str, subject: str, body: str, attachments: list = None, from_name: str = "Nanobot") -> dict:
    """
    Send an email via Mutt, optionally with attachments.

    Args:
        to: Recipient email address
        subject: Email subject
        body: Email body text
        attachments: List of file paths to attach (optional)
        from_name: Sender name (default: Nanobot)

    Returns:
        dict with success status and message
    """
    try:
        # Add signature
        full_body = f"{body}\n\n--\nGesendet von {from_name} via Mutt"

        # Build mutt command
        cmd = ["mutt", "-s", subject]

        # Add attachments if provided
        attachment_count = 0
        if attachments:
            for filepath in attachments:
                if Path(filepath).exists():
                    cmd.extend(["-a", filepath])
                    attachment_count += 1
            # Add -- separator before recipient when using -a
            cmd.append("--")

        cmd.append(to)

        # Send via mutt
        process = subprocess.run(
            cmd,
            input=full_body.encode(),
            capture_output=True,
            timeout=60  # Longer timeout for attachments
        )

        if process.returncode == 0:
            # Log with attachment indicator
            attach_icon = "+📎" if attachment_count > 0 else ""
            log_line = f"{datetime.now():%Y-%m-%d %H:%M:%S} | 📧 EMAIL{attach_icon} | {to} | {subject}"
            with open(LOG_FILE, "a") as f:
                f.write(log_line + "\n")

            return {
                "success": True,
                "message": f"Email sent to {to}",
                "subject": subject,
                "attachments": attachment_count
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


def send_diagram(diagram_path: str, title: str = "Diagram", to: str = "henry.krupp@gmail.com") -> dict:
    """
    Send a diagram (PNG/SVG) as email attachment.

    Args:
        diagram_path: Path to the diagram file
        title: Diagram title for subject
        to: Recipient email

    Returns:
        dict with success status
    """
    if not Path(diagram_path).exists():
        return {"success": False, "error": f"File not found: {diagram_path}"}

    body = f"Hier ist das Diagramm: {title}\n\nDatei: {Path(diagram_path).name}"

    return send_email(
        to=to,
        subject=f"[Nanobot] {title}",
        body=body,
        attachments=[diagram_path]
    )
