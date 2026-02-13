"""
GitHub Watcher
Monitor Issues and PRs for a specific repository
"""

import subprocess
import json
from datetime import datetime
from typing import Optional


def run_gh_command(args: list) -> dict | list | None:
    """Run a gh CLI command and return JSON result."""
    try:
        result = subprocess.run(
            ["gh"] + args,
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode == 0 and result.stdout.strip():
            return json.loads(result.stdout)
        return None
    except Exception as e:
        print(f"gh command failed: {e}")
        return None


def get_repo_summary(repo: str) -> dict:
    """Get repository summary."""
    data = run_gh_command([
        "repo", "view", repo,
        "--json", "name,description,issues,pullRequests,updatedAt"
    ])
    if data:
        return {
            "name": data.get("name"),
            "description": data.get("description", "")[:100],
            "issues_count": data.get("issues", {}).get("totalCount", 0),
            "prs_count": data.get("pullRequests", {}).get("totalCount", 0),
            "updated_at": data.get("updatedAt")
        }
    return {"error": "Could not fetch repo"}


def get_open_issues(repo: str, limit: int = 5) -> list:
    """Get open issues for a repository."""
    data = run_gh_command([
        "issue", "list",
        "--repo", repo,
        "--state", "open",
        "--limit", str(limit),
        "--json", "number,title,author,createdAt,labels,comments"
    ])
    if data:
        return [{
            "number": issue["number"],
            "title": issue["title"][:60],
            "author": issue.get("author", {}).get("login", "unknown"),
            "created": issue["createdAt"][:10],
            "labels": [l["name"] for l in issue.get("labels", [])],
            "comments": issue.get("comments", 0)
        } for issue in data]
    return []


def get_open_prs(repo: str, limit: int = 5) -> list:
    """Get open pull requests for a repository."""
    data = run_gh_command([
        "pr", "list",
        "--repo", repo,
        "--state", "open",
        "--limit", str(limit),
        "--json", "number,title,author,createdAt,reviewDecision,isDraft"
    ])
    if data:
        return [{
            "number": issue["number"],
            "title": issue["title"][:60],
            "author": issue.get("author", {}).get("login", "unknown"),
            "created": issue["createdAt"][:10],
            "draft": issue.get("isDraft", False),
            "review": issue.get("reviewDecision", "PENDING")
        } for issue in data]
    return []


def get_recent_activity(repo: str, days: int = 7) -> dict:
    """Get recent activity summary."""
    # Recent issues
    recent_issues = run_gh_command([
        "issue", "list",
        "--repo", repo,
        "--state", "all",
        "--limit", "20",
        "--json", "number,title,state,createdAt,closedAt"
    ])

    # Recent PRs
    recent_prs = run_gh_command([
        "pr", "list",
        "--repo", repo,
        "--state", "all",
        "--limit", "20",
        "--json", "number,title,state,createdAt,mergedAt"
    ])

    from datetime import timedelta
    cutoff = datetime.now() - timedelta(days=days)
    cutoff_str = cutoff.isoformat()

    new_issues = 0
    closed_issues = 0
    new_prs = 0
    merged_prs = 0

    if recent_issues:
        for issue in recent_issues:
            if issue.get("createdAt", "") > cutoff_str:
                new_issues += 1
            if issue.get("closedAt") and issue["closedAt"] > cutoff_str:
                closed_issues += 1

    if recent_prs:
        for pr in recent_prs:
            if pr.get("createdAt", "") > cutoff_str:
                new_prs += 1
            if pr.get("mergedAt") and pr["mergedAt"] > cutoff_str:
                merged_prs += 1

    return {
        "period_days": days,
        "new_issues": new_issues,
        "closed_issues": closed_issues,
        "new_prs": new_prs,
        "merged_prs": merged_prs
    }


def generate_github_report(repo: str) -> str:
    """Generate a complete GitHub status report."""
    now = datetime.now()
    date_str = now.strftime("%d.%m.%Y %H:%M")

    summary = get_repo_summary(repo)
    issues = get_open_issues(repo, limit=5)
    prs = get_open_prs(repo, limit=5)
    activity = get_recent_activity(repo, days=7)

    report = f"""📊 GitHub Report: {repo}
📅 {date_str}

📈 Repository:
  {summary.get('description', 'No description')}
  Issues: {summary.get('issues_count', 0)} | PRs: {summary.get('prs_count', 0)}

📋 Offene Issues ({len(issues)}):"""

    if issues:
        for issue in issues:
            labels = f" [{', '.join(issue['labels'])}]" if issue['labels'] else ""
            report += f"\n  #{issue['number']} {issue['title']}{labels}"
    else:
        report += "\n  Keine offenen Issues"

    report += f"\n\n🔀 Offene PRs ({len(prs)}):"

    if prs:
        for pr in prs:
            draft = " [DRAFT]" if pr['draft'] else ""
            report += f"\n  #{pr['number']} {pr['title']}{draft}"
    else:
        report += "\n  Keine offenen PRs"

    report += f"""

📊 Letzte 7 Tage:
  Neue Issues: {activity['new_issues']} | Geschlossen: {activity['closed_issues']}
  Neue PRs: {activity['new_prs']} | Gemerged: {activity['merged_prs']}

---
DONE"""

    return report


def watch_and_notify(repo: str, notify_argus: bool = True) -> dict:
    """
    Watch a repository and optionally notify ARGUS proactively.

    Returns:
        dict with report and notification status
    """
    report = generate_github_report(repo)
    activity = get_recent_activity(repo, days=1)

    result = {
        "repo": repo,
        "report": report,
        "new_activity": activity["new_issues"] > 0 or activity["new_prs"] > 0,
        "notified": False
    }

    if notify_argus:
        from .argus_client import on_github_watch_complete

        has_new = activity["new_issues"] > 0 or activity["new_prs"] > 0

        # Notify ARGUS proactively
        on_github_watch_complete(
            repo=repo,
            report=report,
            has_new_issues=has_new
        )
        result["notified"] = True

    return result


if __name__ == "__main__":
    print(generate_github_report("doobidoo/mcp-memory-service"))
