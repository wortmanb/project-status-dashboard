#!/usr/bin/env python3
"""
Project Status Dashboard
A simple web dashboard showing git status across local repositories.
"""

import json
import os
import subprocess
from datetime import datetime
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from typing import Any
import re

GIT_DIR = Path.home() / "git"
PORT = 8765


def run_cmd(cmd: list[str], cwd: str | None = None) -> tuple[str, bool]:
    """Run a command and return (output, success)."""
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=30
        )
        return result.stdout.strip(), result.returncode == 0
    except Exception as e:
        return str(e), False


def get_relative_time(timestamp: int) -> str:
    """Convert Unix timestamp to relative time string."""
    now = datetime.now().timestamp()
    diff = now - timestamp
    
    if diff < 60:
        return "just now"
    elif diff < 3600:
        mins = int(diff / 60)
        return f"{mins} minute{'s' if mins != 1 else ''} ago"
    elif diff < 86400:
        hours = int(diff / 3600)
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    elif diff < 604800:
        days = int(diff / 86400)
        return f"{days} day{'s' if days != 1 else ''} ago"
    elif diff < 2592000:
        weeks = int(diff / 604800)
        return f"{weeks} week{'s' if weeks != 1 else ''} ago"
    else:
        months = int(diff / 2592000)
        return f"{months} month{'s' if months != 1 else ''} ago"


def get_repo_status(repo_path: Path) -> dict[str, Any] | None:
    """Get status info for a git repository."""
    git_dir = repo_path / ".git"
    if not git_dir.exists():
        return None
    
    repo_name = repo_path.name
    cwd = str(repo_path)
    
    # Current branch
    branch, _ = run_cmd(["git", "branch", "--show-current"], cwd)
    if not branch:
        branch, _ = run_cmd(["git", "rev-parse", "--short", "HEAD"], cwd)
        branch = f"detached ({branch})"
    
    # Uncommitted changes
    status, _ = run_cmd(["git", "status", "--porcelain"], cwd)
    changes = status.split("\n") if status else []
    changes = [c for c in changes if c]
    has_changes = len(changes) > 0
    
    # Ahead/behind remote
    ahead, behind = 0, 0
    tracking, _ = run_cmd(["git", "rev-parse", "--abbrev-ref", "@{upstream}"], cwd)
    if tracking:
        ab_output, _ = run_cmd(
            ["git", "rev-list", "--left-right", "--count", f"{tracking}...HEAD"],
            cwd
        )
        if ab_output:
            parts = ab_output.split()
            if len(parts) == 2:
                behind, ahead = int(parts[0]), int(parts[1])
    
    # Last commit
    log_format = "%H|%s|%an|%at"
    log_output, _ = run_cmd(["git", "log", "-1", f"--format={log_format}"], cwd)
    last_commit = None
    if log_output:
        parts = log_output.split("|")
        if len(parts) >= 4:
            last_commit = {
                "hash": parts[0][:7],
                "message": parts[1][:60] + ("..." if len(parts[1]) > 60 else ""),
                "author": parts[2],
                "time": get_relative_time(int(parts[3]))
            }
    
    # GitHub remote check and issues count
    remote_url, _ = run_cmd(["git", "remote", "get-url", "origin"], cwd)
    github_issues = None
    github_url = None
    
    if remote_url and "github.com" in remote_url:
        # Extract owner/repo from URL
        match = re.search(r"github\.com[:/]([^/]+)/([^/.]+)", remote_url)
        if match:
            owner, repo = match.groups()
            repo = repo.replace(".git", "")
            github_url = f"https://github.com/{owner}/{repo}"
            
            # Get open issues count via gh CLI
            issues_output, success = run_cmd(
                ["gh", "issue", "list", "-R", f"{owner}/{repo}", "--state=open", "--json=number"],
                cwd
            )
            if success and issues_output:
                try:
                    issues = json.loads(issues_output)
                    github_issues = len(issues)
                except json.JSONDecodeError:
                    pass
    
    return {
        "name": repo_name,
        "path": cwd,
        "branch": branch,
        "has_changes": has_changes,
        "change_count": len(changes),
        "ahead": ahead,
        "behind": behind,
        "last_commit": last_commit,
        "github_url": github_url,
        "github_issues": github_issues
    }


def get_all_repos() -> list[dict[str, Any]]:
    """Scan git directory for all repositories."""
    repos = []
    if not GIT_DIR.exists():
        return repos
    
    for item in sorted(GIT_DIR.iterdir()):
        if item.is_dir():
            status = get_repo_status(item)
            if status:
                repos.append(status)
    
    return repos


def generate_html() -> str:
    """Generate the dashboard HTML."""
    repos = get_all_repos()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    repo_cards = ""
    for repo in repos:
        # Status indicators
        change_class = "has-changes" if repo["has_changes"] else "clean"
        change_text = f"{repo['change_count']} changed" if repo["has_changes"] else "clean"
        
        sync_parts = []
        if repo["ahead"]:
            sync_parts.append(f"↑{repo['ahead']}")
        if repo["behind"]:
            sync_parts.append(f"↓{repo['behind']}")
        sync_text = " ".join(sync_parts) if sync_parts else "synced"
        sync_class = "out-of-sync" if sync_parts else "synced"
        
        # Last commit
        commit_html = ""
        if repo["last_commit"]:
            c = repo["last_commit"]
            commit_html = f'''
                <div class="commit">
                    <span class="hash">{c["hash"]}</span>
                    <span class="message">{c["message"]}</span>
                    <span class="meta">{c["author"]} · {c["time"]}</span>
                </div>
            '''
        
        # GitHub link and issues
        github_html = ""
        if repo["github_url"]:
            issues_badge = ""
            if repo["github_issues"] is not None:
                issue_class = "has-issues" if repo["github_issues"] > 0 else "no-issues"
                issues_badge = f'<span class="issues {issue_class}">{repo["github_issues"]} issues</span>'
            github_html = f'''
                <div class="github">
                    <a href="{repo["github_url"]}" target="_blank">GitHub</a>
                    {issues_badge}
                </div>
            '''
        
        repo_cards += f'''
            <div class="repo-card">
                <div class="repo-header">
                    <h2>{repo["name"]}</h2>
                    <span class="branch">{repo["branch"]}</span>
                </div>
                <div class="status">
                    <span class="indicator {change_class}">{change_text}</span>
                    <span class="indicator {sync_class}">{sync_text}</span>
                </div>
                {commit_html}
                {github_html}
            </div>
        '''
    
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="refresh" content="60">
    <title>Project Status Dashboard</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: #0d1117;
            color: #c9d1d9;
            min-height: 100vh;
            padding: 2rem;
        }}
        
        header {{
            text-align: center;
            margin-bottom: 2rem;
            padding-bottom: 1rem;
            border-bottom: 1px solid #30363d;
        }}
        
        h1 {{
            color: #58a6ff;
            font-size: 1.8rem;
            margin-bottom: 0.5rem;
        }}
        
        .timestamp {{
            color: #8b949e;
            font-size: 0.9rem;
        }}
        
        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
            gap: 1.5rem;
            max-width: 1400px;
            margin: 0 auto;
        }}
        
        .repo-card {{
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 8px;
            padding: 1.25rem;
            transition: border-color 0.2s;
        }}
        
        .repo-card:hover {{
            border-color: #58a6ff;
        }}
        
        .repo-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1rem;
        }}
        
        .repo-header h2 {{
            color: #f0f6fc;
            font-size: 1.1rem;
            font-weight: 600;
        }}
        
        .branch {{
            background: #1f6feb33;
            color: #58a6ff;
            padding: 0.25rem 0.5rem;
            border-radius: 4px;
            font-size: 0.8rem;
            font-family: monospace;
        }}
        
        .status {{
            display: flex;
            gap: 0.75rem;
            margin-bottom: 1rem;
        }}
        
        .indicator {{
            font-size: 0.85rem;
            padding: 0.2rem 0.5rem;
            border-radius: 4px;
        }}
        
        .clean {{
            background: #23863633;
            color: #3fb950;
        }}
        
        .has-changes {{
            background: #9e6a0333;
            color: #d29922;
        }}
        
        .synced {{
            background: #23863633;
            color: #3fb950;
        }}
        
        .out-of-sync {{
            background: #f8514933;
            color: #f85149;
        }}
        
        .commit {{
            background: #0d1117;
            border-radius: 6px;
            padding: 0.75rem;
            margin-bottom: 0.75rem;
        }}
        
        .commit .hash {{
            font-family: monospace;
            color: #58a6ff;
            font-size: 0.85rem;
        }}
        
        .commit .message {{
            display: block;
            margin: 0.25rem 0;
            color: #c9d1d9;
            font-size: 0.9rem;
        }}
        
        .commit .meta {{
            color: #8b949e;
            font-size: 0.8rem;
        }}
        
        .github {{
            display: flex;
            align-items: center;
            gap: 0.75rem;
        }}
        
        .github a {{
            color: #58a6ff;
            text-decoration: none;
            font-size: 0.9rem;
        }}
        
        .github a:hover {{
            text-decoration: underline;
        }}
        
        .issues {{
            font-size: 0.8rem;
            padding: 0.2rem 0.5rem;
            border-radius: 4px;
        }}
        
        .has-issues {{
            background: #9e6a0333;
            color: #d29922;
        }}
        
        .no-issues {{
            background: #23863633;
            color: #3fb950;
        }}
        
        .empty {{
            text-align: center;
            color: #8b949e;
            padding: 3rem;
        }}
    </style>
</head>
<body>
    <header>
        <h1>📊 Project Status Dashboard</h1>
        <p class="timestamp">Last updated: {timestamp}</p>
    </header>
    
    <div class="grid">
        {repo_cards if repos else '<div class="empty">No repositories found in ~/git/</div>'}
    </div>
</body>
</html>'''


class DashboardHandler(SimpleHTTPRequestHandler):
    """HTTP handler that serves the dashboard."""
    
    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(generate_html().encode())
        elif self.path == "/api/repos":
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(get_all_repos(), indent=2).encode())
        else:
            self.send_error(404)
    
    def log_message(self, format, *args):
        # Quieter logging
        pass


def main():
    """Run the dashboard server."""
    print(f"📊 Project Status Dashboard")
    print(f"   Scanning: {GIT_DIR}")
    print(f"   Server:   http://localhost:{PORT}")
    print(f"   Press Ctrl+C to stop\n")
    
    server = HTTPServer(("0.0.0.0", PORT), DashboardHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.shutdown()


if __name__ == "__main__":
    main()
