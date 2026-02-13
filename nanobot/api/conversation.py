"""
Multi-Turn Conversation Handler
Enables real back-and-forth dialogue between ARGUS and Nanobot
"""

import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field

# Conversation memory file
CONV_MEMORY = Path.home() / ".local/share/p2p-conversations.json"


@dataclass
class Message:
    role: str  # "argus" or "nanobot"
    content: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class Conversation:
    id: str
    topic: str
    messages: list = field(default_factory=list)
    context: dict = field(default_factory=dict)
    turn: int = 0
    status: str = "active"  # active, waiting, done


def load_conversations() -> dict:
    """Load all conversations from memory."""
    if CONV_MEMORY.exists():
        try:
            return json.loads(CONV_MEMORY.read_text())
        except:
            pass
    return {}


def save_conversations(convs: dict):
    """Save conversations to memory."""
    CONV_MEMORY.parent.mkdir(parents=True, exist_ok=True)
    CONV_MEMORY.write_text(json.dumps(convs, indent=2, default=str))


def get_conversation(conv_id: str) -> Optional[dict]:
    """Get a specific conversation."""
    convs = load_conversations()
    return convs.get(conv_id)


def create_conversation(conv_id: str, topic: str, initial_context: dict = None) -> dict:
    """Create a new conversation."""
    convs = load_conversations()
    convs[conv_id] = {
        "id": conv_id,
        "topic": topic,
        "messages": [],
        "context": initial_context or {},
        "turn": 0,
        "status": "active",
        "created_at": datetime.now().isoformat()
    }
    save_conversations(convs)
    return convs[conv_id]


def add_message(conv_id: str, role: str, content: str) -> dict:
    """Add a message to conversation."""
    convs = load_conversations()
    if conv_id not in convs:
        return None

    convs[conv_id]["messages"].append({
        "role": role,
        "content": content,
        "timestamp": datetime.now().isoformat()
    })
    convs[conv_id]["turn"] += 1
    save_conversations(convs)
    return convs[conv_id]


def update_context(conv_id: str, key: str, value) -> dict:
    """Update conversation context."""
    convs = load_conversations()
    if conv_id in convs:
        convs[conv_id]["context"][key] = value
        save_conversations(convs)
    return convs.get(conv_id)


def end_conversation(conv_id: str):
    """Mark conversation as done."""
    convs = load_conversations()
    if conv_id in convs:
        convs[conv_id]["status"] = "done"
        save_conversations(convs)


# ============================================
# GitHub Issue Dialog Logic
# ============================================

def handle_github_dialog(conv_id: str, user_input: str, repo: str = "doobidoo/mcp-memory-service") -> dict:
    """
    Handle a multi-turn GitHub issue discussion.

    Returns:
        {
            "response": str,      # Nanobot's response
            "options": list,      # Suggested next actions
            "waiting_for": str,   # What we're waiting for
            "done": bool          # Is conversation complete?
        }
    """
    conv = get_conversation(conv_id)

    # New conversation
    if not conv:
        conv = create_conversation(conv_id, f"GitHub: {repo}", {"repo": repo})

        # Fetch initial data
        issues = _get_issues(repo)
        update_context(conv_id, "issues", issues)

        if not issues:
            return {
                "response": f"✅ Keine offenen Issues in {repo}. Alles sauber!",
                "options": [],
                "waiting_for": None,
                "done": True
            }

        # Build initial response
        response = f"📋 **{repo}** hat {len(issues)} offene Issues:\n\n"
        for i, issue in enumerate(issues[:5], 1):
            labels = f" `{', '.join(issue['labels'])}`" if issue.get('labels') else ""
            response += f"{i}. **#{issue['number']}** {issue['title'][:50]}{labels}\n"

        response += "\nWelches Issue soll ich genauer anschauen? (Nummer oder 'keins')"

        add_message(conv_id, "nanobot", response)

        return {
            "response": response,
            "options": [f"#{issues[i]['number']}" for i in range(min(5, len(issues)))] + ["keins"],
            "waiting_for": "issue_selection",
            "done": False
        }

    # Continue conversation
    add_message(conv_id, "argus", user_input)
    user_lower = user_input.lower().strip()

    # Check for exit signals
    if any(x in user_lower for x in ["done", "fertig", "ende", "nein", "keins", "nichts"]):
        end_conversation(conv_id)
        return {
            "response": "👍 Alles klar! Bei Fragen einfach melden. DONE",
            "options": [],
            "waiting_for": None,
            "done": True
        }

    # Handle issue selection
    context = conv.get("context", {})
    issues = context.get("issues", [])

    # Extract issue number from input
    import re
    match = re.search(r'#?(\d+)', user_input)

    if match:
        issue_num = int(match.group(1))
        issue = next((i for i in issues if i["number"] == issue_num), None)

        if issue:
            # Fetch detailed info
            details = _get_issue_details(context.get("repo", repo), issue_num)
            update_context(conv_id, "selected_issue", issue_num)

            response = f"📌 **Issue #{issue_num}**: {issue['title']}\n\n"
            response += f"**Erstellt von:** {issue.get('author', 'unknown')}\n"
            response += f"**Erstellt am:** {issue.get('created', 'unknown')}\n"
            response += f"**Kommentare:** {issue.get('comments', 0)}\n"

            if details.get("body"):
                body = details["body"][:300] + "..." if len(details.get("body", "")) > 300 else details.get("body", "")
                response += f"\n**Beschreibung:**\n{body}\n"

            response += "\nWas möchtest du tun?\n"
            response += "- 'kommentare' - Letzte Kommentare anzeigen\n"
            response += "- 'analysieren' - Issue analysieren lassen\n"
            response += "- 'zurück' - Andere Issues anschauen\n"
            response += "- 'fertig' - Dialog beenden"

            add_message(conv_id, "nanobot", response)

            return {
                "response": response,
                "options": ["kommentare", "analysieren", "zurück", "fertig"],
                "waiting_for": "action_selection",
                "done": False
            }

    # Handle actions on selected issue
    selected = context.get("selected_issue")

    if selected and "kommentar" in user_lower:
        comments = _get_issue_comments(context.get("repo", repo), selected)
        if comments:
            response = f"💬 Letzte Kommentare zu #{selected}:\n\n"
            for c in comments[:3]:
                response += f"**{c['author']}** ({c['date']}):\n{c['body'][:150]}...\n\n"
        else:
            response = f"Keine Kommentare zu #{selected}."

        response += "\nNoch etwas? ('analysieren', 'zurück', 'fertig')"
        add_message(conv_id, "nanobot", response)

        return {
            "response": response,
            "options": ["analysieren", "zurück", "fertig"],
            "waiting_for": "action_selection",
            "done": False
        }

    if selected and "analy" in user_lower:
        issue = next((i for i in issues if i["number"] == selected), {})
        response = f"🔍 **Analyse Issue #{selected}:**\n\n"
        response += f"- Typ: {'Bug' if 'bug' in str(issue.get('labels', [])).lower() else 'Feature/Enhancement'}\n"
        response += f"- Alter: {issue.get('created', 'unbekannt')}\n"
        response += f"- Aktivität: {issue.get('comments', 0)} Kommentare\n"
        response += f"- Priority: {'Hoch' if issue.get('comments', 0) > 5 else 'Normal'}\n"
        response += "\nSoll ich Claude Code bitten, einen Lösungsvorschlag zu erstellen? ('ja'/'nein')"

        add_message(conv_id, "nanobot", response)
        update_context(conv_id, "waiting_for_claude", True)

        return {
            "response": response,
            "options": ["ja", "nein"],
            "waiting_for": "claude_decision",
            "done": False
        }

    # Handle "ja" - ask Claude Code for solution
    if context.get("waiting_for_claude") and user_lower in ["ja", "yes", "ok"]:
        issue = next((i for i in issues if i["number"] == selected), {})
        update_context(conv_id, "waiting_for_claude", False)

        # Build prompt for Claude Code
        prompt = f"""Analysiere GitHub Issue #{selected} aus {context.get('repo', repo)}:

Titel: {issue.get('title', 'Unknown')}
Labels: {', '.join(issue.get('labels', []))}
Erstellt: {issue.get('created', 'unknown')}

Gib einen kurzen Lösungsvorschlag (max 5 Zeilen). Antworte auf Deutsch."""

        # Call Claude Code
        from .server import ask_claude
        success, claude_response = ask_claude(prompt, timeout=90)

        if success:
            response = f"🤖 **Claude Code Vorschlag für #{selected}:**\n\n{claude_response}\n\n"
            response += "Noch etwas? ('zurück' für andere Issues, 'fertig' zum Beenden)"
        else:
            response = f"❌ Claude Code konnte nicht antworten: {claude_response}\n\n"
            response += "Versuche es später nochmal. ('zurück', 'fertig')"

        add_message(conv_id, "nanobot", response)

        return {
            "response": response,
            "options": ["zurück", "fertig"],
            "waiting_for": "post_claude",
            "done": False
        }

    # Handle "nein" - skip Claude Code
    if context.get("waiting_for_claude") and user_lower in ["nein", "no", "nee"]:
        update_context(conv_id, "waiting_for_claude", False)
        response = "👍 Ok, kein Problem. Was möchtest du tun?\n"
        response += "- 'zurück' - Andere Issues anschauen\n"
        response += "- 'fertig' - Dialog beenden"

        add_message(conv_id, "nanobot", response)

        return {
            "response": response,
            "options": ["zurück", "fertig"],
            "waiting_for": "action_selection",
            "done": False
        }

    if "zurück" in user_lower:
        # Reset to issue list
        update_context(conv_id, "selected_issue", None)
        update_context(conv_id, "waiting_for_claude", False)
        response = "📋 Zurück zur Issue-Liste:\n\n"
        for i, issue in enumerate(issues[:5], 1):
            response += f"{i}. **#{issue['number']}** {issue['title'][:50]}\n"
        response += "\nWelches Issue? (Nummer oder 'fertig')"

        add_message(conv_id, "nanobot", response)

        return {
            "response": response,
            "options": [f"#{issues[i]['number']}" for i in range(min(5, len(issues)))] + ["fertig"],
            "waiting_for": "issue_selection",
            "done": False
        }

    # Default response
    response = "Das habe ich nicht verstanden. Sag mir eine Issue-Nummer, 'zurück' oder 'fertig'."
    add_message(conv_id, "nanobot", response)

    return {
        "response": response,
        "options": ["zurück", "fertig"],
        "waiting_for": "clarification",
        "done": False
    }


def _get_issues(repo: str) -> list:
    """Fetch issues via gh CLI."""
    try:
        result = subprocess.run(
            ["gh", "issue", "list", "--repo", repo, "--state", "open",
             "--limit", "10", "--json", "number,title,author,createdAt,labels,comments"],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            issues = json.loads(result.stdout)
            return [{
                "number": i["number"],
                "title": i["title"],
                "author": i.get("author", {}).get("login", "unknown"),
                "created": i["createdAt"][:10],
                "labels": [l["name"] for l in i.get("labels", [])],
                "comments": len(i.get("comments", []))
            } for i in issues]
    except:
        pass
    return []


def _get_issue_details(repo: str, number: int) -> dict:
    """Fetch issue details."""
    try:
        result = subprocess.run(
            ["gh", "issue", "view", str(number), "--repo", repo, "--json", "title,body,comments"],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            return json.loads(result.stdout)
    except:
        pass
    return {}


def _get_issue_comments(repo: str, number: int) -> list:
    """Fetch issue comments."""
    try:
        result = subprocess.run(
            ["gh", "issue", "view", str(number), "--repo", repo, "--json", "comments"],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            return [{
                "author": c.get("author", {}).get("login", "unknown"),
                "body": c.get("body", ""),
                "date": c.get("createdAt", "")[:10]
            } for c in data.get("comments", [])[-5:]]
    except:
        pass
    return []
