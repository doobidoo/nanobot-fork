"""
Daily Digest Generator
Creates a summary of the day's activities for ARGUS
"""

import subprocess
from datetime import datetime
from pathlib import Path


def get_git_activity() -> str:
    """Get today's git commits across repositories."""
    repos_dir = Path.home() / "repositories"
    today = datetime.now().strftime("%Y-%m-%d")
    activity = []

    for repo in repos_dir.iterdir():
        if repo.is_dir() and (repo / ".git").exists():
            try:
                result = subprocess.run(
                    ["git", "log", "--oneline", f"--since={today}", "--pretty=format:%s"],
                    cwd=repo,
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.stdout.strip():
                    commits = result.stdout.strip().split('\n')
                    activity.append(f"  {repo.name}: {len(commits)} commits")
                    for commit in commits[:3]:  # Max 3 per repo
                        activity.append(f"    - {commit[:60]}")
            except:
                pass

    return '\n'.join(activity) if activity else "  Keine Git-Aktivität heute"


def get_system_status() -> str:
    """Get basic system status."""
    status = []

    # Disk space
    try:
        result = subprocess.run(
            ["df", "-h", "/"],
            capture_output=True,
            text=True,
            timeout=5
        )
        lines = result.stdout.strip().split('\n')
        if len(lines) > 1:
            parts = lines[1].split()
            status.append(f"  Disk: {parts[4]} belegt ({parts[3]} frei)")
    except:
        pass

    # Uptime
    try:
        uptime = Path("/proc/uptime").read_text().split()[0]
        hours = int(float(uptime) / 3600)
        status.append(f"  Uptime: {hours}h")
    except:
        pass

    # Services
    services = ["claude-tmux", "nanobot-api", "p2p-logs-export.timer"]
    running = []
    for svc in services:
        try:
            result = subprocess.run(
                ["systemctl", "--user", "is-active", svc],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.stdout.strip() == "active":
                running.append(svc.replace(".timer", ""))
        except:
            pass

    if running:
        status.append(f"  Services: {', '.join(running)}")

    return '\n'.join(status) if status else "  Status nicht verfügbar"


def get_p2p_summary() -> str:
    """Get P2P exchange summary."""
    log_file = Path.home() / ".local/share/nanobot-p2p.log"

    if not log_file.exists():
        return "  Keine P2P-Aktivität"

    try:
        lines = log_file.read_text().strip().split('\n')
        today = datetime.now().strftime("%Y-%m-%d")
        today_lines = [l for l in lines if l.startswith(today)]

        return f"  {len(today_lines)} Exchanges heute"
    except:
        return "  P2P-Log nicht lesbar"


def generate_daily_digest() -> str:
    """Generate the complete daily digest."""
    now = datetime.now()
    date_str = now.strftime("%d.%m.%Y")
    time_str = now.strftime("%H:%M")

    digest = f"""📊 Daily Digest - {date_str} ({time_str})

🔧 System Status:
{get_system_status()}

📝 Git Aktivität:
{get_git_activity()}

🔗 P2P Kommunikation:
{get_p2p_summary()}

---
DONE"""

    return digest


if __name__ == "__main__":
    print(generate_daily_digest())
