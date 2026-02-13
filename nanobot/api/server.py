"""
Nanobot P2P API Server
Enables peer-to-peer communication with ARGUS and other services.
"""

import asyncio
import subprocess
import os
from pathlib import Path
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional

app = FastAPI(
    title="Nanobot API",
    description="P2P API for Nanobot - enables communication with ARGUS and other peers",
    version="1.0.0"
)

# Paths
SKILL_SCRIPTS = Path.home() / "repositories/nanobot-fork/nanobot/skills/claude-code/scripts"
CLAUDE_SESSION = "claude"


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
async def ask(request: PromptRequest):
    """
    Send a prompt to Claude Code and get the response.

    Used by ARGUS for P2P communication.
    """
    # Check session first
    session_status = check_tmux_session(CLAUDE_SESSION)
    if session_status == "stopped":
        raise HTTPException(
            status_code=503,
            detail="Claude tmux session not running. Start with: systemctl --user start claude-tmux"
        )

    success, response = ask_claude(request.prompt, request.timeout)

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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
