"""
Nanobot P2P API Server
Enables peer-to-peer communication with ARGUS and other services.
"""

import asyncio
import subprocess
import os
import logging
from datetime import datetime
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from typing import Optional, List

# Setup logging
LOG_DIR = Path.home() / ".local/share"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "nanobot-p2p.log"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("p2p")

app = FastAPI(
    title="Nanobot API",
    description="P2P API for Nanobot - enables communication with ARGUS and other peers",
    version="1.1.0"
)

# Paths
SKILL_SCRIPTS = Path.home() / "repositories/nanobot-fork/nanobot/skills/claude-code/scripts"
CLAUDE_SESSION = "claude"


def log_exchange(direction: str, source: str, target: str, message: str, response: str = None):
    """Log P2P exchanges for debugging and monitoring."""
    if response:
        logger.info(f"{direction} | {source} → {target} | Q: {message[:100]}... | A: {response[:100]}...")
    else:
        logger.info(f"{direction} | {source} → {target} | {message[:200]}")


class PromptRequest(BaseModel):
    prompt: str
    timeout: int = 60


class SkillRequest(BaseModel):
    skill: str
    args: Optional[str] = None


class StatusResponse(BaseModel):
    status: str
    claude_session: str
    services: dict


class PromptResponse(BaseModel):
    success: bool
    response: Optional[str] = None
    error: Optional[str] = None


def check_tmux_session(session: str) -> str:
    """Check if tmux session exists and get status."""
    try:
        result = subprocess.run(
            ["tmux", "has-session", "-t", session],
            capture_output=True,
            timeout=5
        )
        if result.returncode == 0:
            # Check if Claude is ready
            status_script = SKILL_SCRIPTS / "claude-status.sh"
            if status_script.exists():
                status = subprocess.run(
                    [str(status_script)],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                return status.stdout.strip()
            return "running"
        return "stopped"
    except Exception:
        return "error"


def ask_claude(prompt: str, timeout: int = 60) -> tuple[bool, str]:
    """Send prompt to Claude Code via tmux and get response."""
    ask_script = SKILL_SCRIPTS / "ask-claude.sh"

    if not ask_script.exists():
        return False, f"Script not found: {ask_script}"

    try:
        result = subprocess.run(
            [str(ask_script), prompt, str(timeout)],
            capture_output=True,
            text=True,
            timeout=timeout + 10
        )

        if result.returncode == 0:
            # Extract response (lines starting with ●)
            lines = result.stdout.split('\n')
            response_lines = [
                line[2:].strip() if line.startswith('● ') else line[1:].strip()
                for line in lines
                if line.startswith('●')
            ]
            response = '\n'.join(response_lines) if response_lines else result.stdout
            return True, response
        else:
            return False, result.stderr or "Unknown error"

    except subprocess.TimeoutExpired:
        return False, "Request timed out"
    except Exception as e:
        return False, str(e)


@app.get("/")
async def root():
    """API root - basic info."""
    return {
        "service": "Nanobot API",
        "version": "1.0.0",
        "endpoints": ["/status", "/ask", "/skill/{name}"]
    }


@app.get("/health")
async def health():
    """Health check endpoint for monitoring."""
    return {"status": "ok"}


@app.get("/status", response_model=StatusResponse)
async def status():
    """Get Nanobot and Claude Code status."""
    claude_status = check_tmux_session(CLAUDE_SESSION)

    return StatusResponse(
        status="ok",
        claude_session=claude_status,
        services={
            "api": "running",
            "claude_tmux": claude_status,
            "skills": "available" if SKILL_SCRIPTS.exists() else "missing"
        }
    )


@app.post("/ask", response_model=PromptResponse)
async def ask(request: PromptRequest, req: Request):
    """
    Send a prompt to Claude Code and get the response.

    Used by ARGUS for P2P communication.
    """
    # Identify caller
    caller = req.headers.get("X-Source", "unknown")

    # Check session first
    session_status = check_tmux_session(CLAUDE_SESSION)
    if session_status == "stopped":
        log_exchange("IN", caller, "nanobot", request.prompt, "ERROR: session stopped")
        raise HTTPException(
            status_code=503,
            detail="Claude tmux session not running. Start with: systemctl --user start claude-tmux"
        )

    success, response = ask_claude(request.prompt, request.timeout)

    # Log the exchange
    log_exchange("IN", caller, "claude", request.prompt, response if success else f"ERROR: {response}")

    return PromptResponse(
        success=success,
        response=response if success else None,
        error=None if success else response
    )


@app.post("/skill/{skill_name}")
async def run_skill(skill_name: str, request: Optional[SkillRequest] = None):
    """
    Run a Nanobot skill by name.

    Skills are located in nanobot/skills/{skill_name}/
    """
    skills_dir = Path.home() / "repositories/nanobot-fork/nanobot/skills"
    skill_path = skills_dir / skill_name

    if not skill_path.exists():
        raise HTTPException(status_code=404, detail=f"Skill not found: {skill_name}")

    # For now, delegate to Claude Code with skill context
    skill_md = skill_path / "SKILL.md"
    if skill_md.exists():
        prompt = f"Use the {skill_name} skill"
        if request and request.args:
            prompt += f": {request.args}"

        success, response = ask_claude(prompt, timeout=60)
        return {
            "skill": skill_name,
            "success": success,
            "response": response if success else None,
            "error": None if success else response
        }

    raise HTTPException(status_code=500, detail=f"Skill {skill_name} has no SKILL.md")


@app.get("/skills")
async def list_skills():
    """List available Nanobot skills."""
    skills_dir = Path.home() / "repositories/nanobot-fork/nanobot/skills"

    if not skills_dir.exists():
        return {"skills": []}

    skills = []
    for path in skills_dir.iterdir():
        if path.is_dir() and (path / "SKILL.md").exists():
            skills.append({
                "name": path.name,
                "path": str(path)
            })

    return {"skills": skills}


@app.get("/logs")
async def get_logs(lines: int = 50):
    """
    Get recent P2P exchange logs.

    Use this to monitor what's being exchanged between ARGUS and Nanobot.
    """
    if not LOG_FILE.exists():
        return {"logs": [], "file": str(LOG_FILE)}

    try:
        with open(LOG_FILE, 'r') as f:
            all_lines = f.readlines()
            recent = all_lines[-lines:] if len(all_lines) > lines else all_lines
            return {
                "logs": [line.strip() for line in recent],
                "total_lines": len(all_lines),
                "showing": len(recent),
                "file": str(LOG_FILE)
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/logs")
async def clear_logs():
    """Clear the P2P exchange logs."""
    if LOG_FILE.exists():
        LOG_FILE.unlink()
    return {"status": "cleared"}


@app.get("/monitor")
async def monitor():
    """Serve the P2P Monitor HTML page."""
    from fastapi.responses import HTMLResponse
    monitor_file = Path.home() / "p2p-monitor/index.html"
    if monitor_file.exists():
        # Update URLs in HTML to use relative paths
        html = monitor_file.read_text()
        # Replace localhost URLs with relative paths (same origin)
        html = html.replace("http://127.0.0.1:8888", "")
        html = html.replace("http://127.0.0.1:3200", "http://127.0.0.1:3200")  # ARGUS stays absolute
        return HTMLResponse(content=html)
    raise HTTPException(status_code=404, detail="Monitor page not found")


# ============================================
# Daily Digest Endpoint (with Safeguards)
# ============================================

@app.get("/digest")
async def daily_digest(conversation_id: str = None):
    """
    Generate daily digest with P2P safeguards.

    Called by ARGUS for daily summary.
    Includes safeguards to prevent infinite loops.
    """
    from .p2p_protocol import (
        check_safeguards, start_conversation, record_turn,
        end_conversation, cleanup_old_conversations
    )
    from .daily_digest import generate_daily_digest

    # Generate conversation ID if not provided
    if not conversation_id:
        conversation_id = f"digest-{datetime.now().strftime('%Y%m%d-%H%M')}"

    # Check safeguards
    should_respond, reason = check_safeguards(conversation_id, "argus")
    if not should_respond:
        log_exchange("BLOCKED", "argus", "nanobot", f"digest request: {reason}")
        return {
            "success": False,
            "blocked": True,
            "reason": reason,
            "conversation_id": conversation_id
        }

    # Start/continue conversation
    start_conversation(conversation_id, "argus")

    # Generate digest
    try:
        digest = generate_daily_digest()

        # Record this turn
        record_turn(conversation_id)

        # End conversation (digest is always one-shot)
        end_conversation(conversation_id, "digest_complete")

        # Cleanup old conversations
        cleanup_old_conversations(24)

        # Log the exchange
        log_exchange("IN", "argus", "nanobot", "digest request", digest[:100])

        return {
            "success": True,
            "digest": digest,
            "conversation_id": conversation_id,
            "turns": 1,
            "completed": True
        }

    except Exception as e:
        end_conversation(conversation_id, f"error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/github/{owner}/{repo}")
async def github_watch(owner: str, repo: str, conversation_id: str = None):
    """
    Get GitHub Issues/PR report for a repository.

    Called by ARGUS for repo monitoring.
    Includes safeguards to prevent infinite loops.
    """
    from .p2p_protocol import (
        check_safeguards, start_conversation, record_turn,
        end_conversation, cleanup_old_conversations
    )
    from .github_watcher import generate_github_report

    full_repo = f"{owner}/{repo}"

    # Generate conversation ID if not provided
    if not conversation_id:
        conversation_id = f"github-{owner}-{repo}-{datetime.now().strftime('%Y%m%d-%H%M')}"

    # Check safeguards
    should_respond, reason = check_safeguards(conversation_id, "argus")
    if not should_respond:
        log_exchange("BLOCKED", "argus", "nanobot", f"github watch {full_repo}: {reason}")
        return {
            "success": False,
            "blocked": True,
            "reason": reason,
            "conversation_id": conversation_id
        }

    # Start conversation
    start_conversation(conversation_id, "argus")

    try:
        report = generate_github_report(full_repo)

        # Record turn and end
        record_turn(conversation_id)
        end_conversation(conversation_id, "github_report_complete")
        cleanup_old_conversations(24)

        # Log exchange
        log_exchange("IN", "argus", "nanobot", f"github watch {full_repo}", report[:100])

        return {
            "success": True,
            "repo": full_repo,
            "report": report,
            "conversation_id": conversation_id,
            "completed": True
        }

    except Exception as e:
        end_conversation(conversation_id, f"error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# Multi-Turn Conversation Endpoint
# ============================================

@app.post("/chat/{owner}/{repo}")
async def github_chat(owner: str, repo: str, request: PromptRequest):
    """
    Multi-turn GitHub issue dialog.

    Supports real back-and-forth conversation:
    - Start with: {"prompt": "start"} or empty prompt
    - Continue with: issue numbers, actions, or responses
    - End with: "fertig", "done", "nein"

    Returns options for next steps to enable structured dialog.
    """
    from .conversation import handle_github_dialog

    full_repo = f"{owner}/{repo}"

    # Generate conversation ID based on repo
    conv_id = f"chat-{owner}-{repo}"

    # Handle the dialog
    user_input = request.prompt or "start"
    result = handle_github_dialog(conv_id, user_input, full_repo)

    # Log the exchange
    log_exchange("CHAT", "argus", "nanobot",
                 f"{full_repo}: {user_input[:50]}",
                 result["response"][:100] if result.get("response") else "")

    return {
        "success": True,
        "repo": full_repo,
        "conversation_id": conv_id,
        "response": result["response"],
        "options": result.get("options", []),
        "waiting_for": result.get("waiting_for"),
        "done": result.get("done", False)
    }


@app.delete("/chat/{owner}/{repo}")
async def end_chat(owner: str, repo: str):
    """End a multi-turn conversation and clear state."""
    from .conversation import end_conversation, get_conversation

    conv_id = f"chat-{owner}-{repo}"
    conv = get_conversation(conv_id)

    if conv:
        end_conversation(conv_id)
        return {
            "success": True,
            "message": f"Conversation {conv_id} ended",
            "turns": conv.get("turn", 0)
        }

    return {
        "success": False,
        "message": f"No active conversation for {owner}/{repo}"
    }


@app.get("/chat/{owner}/{repo}/history")
async def chat_history(owner: str, repo: str):
    """Get conversation history for a repo dialog."""
    from .conversation import get_conversation

    conv_id = f"chat-{owner}-{repo}"
    conv = get_conversation(conv_id)

    if conv:
        return {
            "success": True,
            "conversation_id": conv_id,
            "topic": conv.get("topic"),
            "status": conv.get("status"),
            "turns": conv.get("turn", 0),
            "messages": conv.get("messages", []),
            "context": conv.get("context", {})
        }

    return {
        "success": False,
        "message": f"No conversation found for {owner}/{repo}"
    }


@app.get("/p2p/state")
async def p2p_state():
    """Get current P2P protocol state (for debugging)."""
    from .p2p_protocol import load_state
    return load_state()


@app.delete("/p2p/state")
async def clear_p2p_state():
    """Clear P2P protocol state."""
    from .p2p_protocol import STATE_FILE
    if STATE_FILE.exists():
        STATE_FILE.unlink()
    return {"status": "cleared"}


# ============================================
# Proactive Messaging: Nanobot → ARGUS
# ============================================

class MessageToArgus(BaseModel):
    message: str
    priority: str = "normal"  # normal, high, critical


@app.post("/argus/notify")
async def notify_argus(request: MessageToArgus):
    """
    Send a proactive notification to ARGUS.

    Nanobot initiates contact with ARGUS.
    """
    from .argus_client import notify_argus as do_notify

    result = do_notify(
        title="Nanobot Nachricht",
        body=request.message,
        priority=request.priority
    )

    log_exchange("OUT", "nanobot", "argus", request.message,
                 result.get("message", "")[:100] if result.get("success") else "FAILED")

    return result


@app.post("/argus/ask")
async def ask_argus_endpoint(request: PromptRequest):
    """
    Ask ARGUS a question and get response.

    Nanobot asks ARGUS for help/information.
    """
    from .argus_client import ask_argus

    response = ask_argus(request.prompt)

    log_exchange("OUT", "nanobot", "argus", f"Frage: {request.prompt}",
                 response[:100] if response else "No response")

    return {
        "success": response is not None,
        "question": request.prompt,
        "response": response
    }


@app.post("/argus/report")
async def report_to_argus(report_type: str, content: str):
    """
    Send a report to ARGUS.

    Types: github, digest, discovery, error, success
    """
    from .argus_client import report_to_argus as do_report

    result = do_report(report_type, content)

    log_exchange("OUT", "nanobot", "argus", f"Report ({report_type})",
                 result.get("message", "")[:100] if result.get("success") else "FAILED")

    return result


@app.get("/argus/status")
async def argus_status():
    """Check if ARGUS is online."""
    from .argus_client import check_argus

    online = check_argus()
    return {
        "peer": "argus",
        "status": "online" if online else "offline",
        "url": "http://127.0.0.1:3200"
    }


@app.post("/github/{owner}/{repo}/watch-and-notify")
async def github_watch_and_notify(owner: str, repo: str):
    """
    Watch GitHub repo AND proactively notify ARGUS.

    This is the bidirectional version - Nanobot watches and
    automatically tells ARGUS about the results.
    """
    from .github_watcher import watch_and_notify

    full_repo = f"{owner}/{repo}"

    result = watch_and_notify(full_repo, notify_argus=True)

    log_exchange("OUT", "nanobot", "argus",
                 f"GitHub Watch: {full_repo}",
                 f"Notified: {result.get('notified')}, New: {result.get('new_activity')}")

    return result


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
