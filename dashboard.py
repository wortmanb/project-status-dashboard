#!/usr/bin/env python3
"""
Project Status Dashboard
A simple Flask app showing status of all git repos in ~/git/
"""

import os
import subprocess
import json
from datetime import datetime, timezone
from pathlib import Path
from flask import Flask, render_template_string, jsonify

app = Flask(__name__)

GIT_DIR = Path.home() / "git"

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="refresh" content="60">
    <title>Project Status Dashboard</title>
    <style>
        :root {
            --bg-primary: #0d1117;
            --bg-secondary: #161b22;
            --bg-tertiary: #21262d;
            --border: #30363d;
            --text-primary: #e6edf3;
            --text-secondary: #8b949e;
            --accent-green: #3fb950;
            --accent-yellow: #d29922;
            --accent-red: #f85149;
            --accent-blue: #58a6ff;
            --accent-purple: #a371f7;
        }
        
        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            line-height: 1.6;
            padding: 2rem;
            min-height: 100vh;
        }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
        }
        
        header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 2rem;
            padding-bottom: 1rem;
            border-bottom: 1px solid var(--border);
        }
        
        h1 {
            font-size: 1.75rem;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 0.75rem;
        }
        
        h1::before {
            content: "📊";
        }
        
        .timestamp {
            color: var(--text-secondary);
            font-size: 0.875rem;
        }
        
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(420px, 1fr));
            gap: 1.25rem;
        }
        
        .card {
            background: var(--bg-secondary);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 1.25rem;
            transition: border-color 0.2s;
        }
        
        .card:hover {
            border-color: var(--accent-blue);
        }
        
        .card-header {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 1rem;
        }
        
        .repo-name {
            font-size: 1.125rem;
            font-weight: 600;
            color: var(--accent-blue);
            text-decoration: none;
        }
        
        .repo-name:hover {
            text-decoration: underline;
        }
        
        .branch {
            display: inline-flex;
            align-items: center;
            gap: 0.35rem;
            background: var(--bg-tertiary);
            padding: 0.25rem 0.6rem;
            border-radius: 20px;
            font-size: 0.8rem;
            color: var(--text-secondary);
        }
        
        .branch::before {
            content: "⎇";
            font-size: 0.75rem;
        }
        
        .stats {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 0.75rem;
            margin-bottom: 1rem;
        }
        
        .stat {
            background: var(--bg-tertiary);
            padding: 0.6rem;
            border-radius: 6px;
            text-align: center;
        }
        
        .stat-label {
            font-size: 0.7rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--text-secondary);
            margin-bottom: 0.25rem;
        }
        
        .stat-value {
            font-weight: 600;
            font-size: 0.95rem;
        }
        
        .stat-value.clean { color: var(--accent-green); }
        .stat-value.dirty { color: var(--accent-yellow); }
        .stat-value.ahead { color: var(--accent-purple); }
        .stat-value.behind { color: var(--accent-red); }
        .stat-value.synced { color: var(--text-secondary); }
        .stat-value.issues { color: var(--accent-yellow); }
        .stat-value.no-issues { color: var(--text-secondary); }
        
        .commit {
            background: var(--bg-tertiary);
            border-radius: 6px;
            padding: 0.75rem;
            font-size: 0.85rem;
        }
        
        .commit-header {
            display: flex;
            justify-content: space-between;
            margin-bottom: 0.35rem;
            color: var(--text-secondary);
            font-size: 0.75rem;
        }
        
        .commit-message {
            color: var(--text-primary);
            word-break: break-word;
        }
        
        .error {
            color: var(--accent-red);
            font-size: 0.85rem;
        }
        
        @media (max-width: 768px) {
            body { padding: 1rem; }
            .grid { grid-template-columns: 1fr; }
            header { flex-direction: column; gap: 0.5rem; align-items: flex-start; }
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>Project Status</h1>
            <span class="timestamp">Updated: {{ timestamp }}</span>
        </header>
        <div class="grid">
            {% for repo in repos %}
            <div class="card">
                <div class="card-header">
                    {% if repo.github_url %}
                    <a href="{{ repo.github_url }}" class="repo-name" target="_blank">{{ repo.name }}</a>
                    {% else %}
                    <span class="repo-name">{{ repo.name }}</span>
                    {% endif %}
                    <span class="branch">{{ repo.branch }}</span>
                </div>
                
                {% if repo.error %}
                <p class="error">{{ repo.error }}</p>
                {% else %}
                <div class="stats">
                    <div class="stat">
                        <div class="stat-label">Changes</div>
                        <div class="stat-value {{ 'dirty' if repo.changes_count > 0 else 'clean' }}">
                            {{ repo.changes_count if repo.changes_count > 0 else '✓ Clean' }}
                        </div>
                    </div>
                    <div class="stat">
                        <div class="stat-label">Sync</div>
                        <div class="stat-value 
                            {%- if repo.ahead > 0 and repo.behind > 0 %} dirty
                            {%- elif repo.ahead > 0 %} ahead
                            {%- elif repo.behind > 0 %} behind
                            {%- else %} synced{% endif %}">
                            {% if repo.ahead > 0 or repo.behind > 0 %}
                                {% if repo.ahead > 0 %}↑{{ repo.ahead }}{% endif %}
                                {% if repo.behind > 0 %}↓{{ repo.behind }}{% endif %}
                            {% else %}
                                ✓ Synced
                            {% endif %}
                        </div>
                    </div>
                    <div class="stat">
                        <div class="stat-label">Issues</div>
                        <div class="stat-value {{ 'issues' if repo.issues_count and repo.issues_count > 0 else 'no-issues' }}">
                            {{ repo.issues_count if repo.issues_count is not none else '—' }}
                        </div>
                    </div>
                </div>
                
                <div class="commit">
                    <div class="commit-header">
                        <span>{{ repo.last_author }}</span>
                        <span>{{ repo.last_time }}</span>
                    </div>
                    <div class="commit-message">{{ repo.last_message }}</div>
                </div>
                {% endif %}
            </div>
            {% endfor %}
        </div>
    </div>
</body>
</html>
"""


def run_git(repo_path, *args):
    """Run a git command and return stdout, or None on error."""
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_path)] + list(args),
            capture_output=True,
            text=True,
            timeout=10
        )
        return result.stdout.strip() if result.returncode == 0 else None
    except Exception:
        return None


def get_github_url(repo_path):
    """Extract GitHub URL from remote origin."""
    remote = run_git(repo_path, "remote", "get-url", "origin")
    if not remote:
        return None
    
    # Convert SSH URL to HTTPS
    if remote.startswith("git@github.com:"):
        return remote.replace("git@github.com:", "https://github.com/").rstrip(".git")
    elif "github.com" in remote:
        return remote.rstrip(".git")
    return None


def get_github_issues_count(repo_path):
    """Get open issues count using gh CLI."""
    github_url = get_github_url(repo_path)
    if not github_url or "github.com" not in github_url:
        return None
    
    # Extract owner/repo from URL
    parts = github_url.rstrip("/").split("/")
    if len(parts) < 2:
        return None
    owner_repo = f"{parts[-2]}/{parts[-1]}"
    
    try:
        result = subprocess.run(
            ["gh", "issue", "list", "--repo", owner_repo, "--state", "open", "--json", "number"],
            capture_output=True,
            text=True,
            timeout=15
        )
        if result.returncode == 0:
            issues = json.loads(result.stdout)
            return len(issues)
    except Exception:
        pass
    return None


def get_relative_time(iso_timestamp):
    """Convert ISO timestamp to relative time string."""
    try:
        # Parse ISO format
        dt = datetime.fromisoformat(iso_timestamp.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        diff = now - dt
        
        seconds = diff.total_seconds()
        if seconds < 60:
            return "just now"
        elif seconds < 3600:
            mins = int(seconds / 60)
            return f"{mins}m ago"
        elif seconds < 86400:
            hours = int(seconds / 3600)
            return f"{hours}h ago"
        elif seconds < 604800:
            days = int(seconds / 86400)
            return f"{days}d ago"
        elif seconds < 2592000:
            weeks = int(seconds / 604800)
            return f"{weeks}w ago"
        else:
            months = int(seconds / 2592000)
            return f"{months}mo ago"
    except Exception:
        return "unknown"


def get_repo_status(repo_path):
    """Get complete status for a single repo."""
    name = repo_path.name
    
    # Skip if not a git repo
    if not (repo_path / ".git").exists():
        return None
    
    repo = {
        "name": name,
        "branch": "unknown",
        "changes_count": 0,
        "ahead": 0,
        "behind": 0,
        "last_message": "",
        "last_author": "",
        "last_time": "",
        "issues_count": None,
        "github_url": None,
        "error": None
    }
    
    # Branch
    branch = run_git(repo_path, "rev-parse", "--abbrev-ref", "HEAD")
    repo["branch"] = branch or "detached"
    
    # Uncommitted changes
    status = run_git(repo_path, "status", "--porcelain")
    if status is not None:
        changes = [l for l in status.split("\n") if l.strip()]
        repo["changes_count"] = len(changes)
    
    # Ahead/behind - first fetch to get accurate count
    run_git(repo_path, "fetch", "--quiet")
    tracking = run_git(repo_path, "rev-parse", "--abbrev-ref", "@{upstream}")
    if tracking:
        ahead_behind = run_git(repo_path, "rev-list", "--left-right", "--count", f"HEAD...@{{upstream}}")
        if ahead_behind:
            parts = ahead_behind.split()
            if len(parts) == 2:
                repo["ahead"] = int(parts[0])
                repo["behind"] = int(parts[1])
    
    # Last commit
    log_format = run_git(repo_path, "log", "-1", "--format=%s|%an|%aI")
    if log_format:
        parts = log_format.split("|")
        if len(parts) >= 3:
            repo["last_message"] = parts[0][:80] + ("..." if len(parts[0]) > 80 else "")
            repo["last_author"] = parts[1]
            repo["last_time"] = get_relative_time(parts[2])
    
    # GitHub URL and issues
    repo["github_url"] = get_github_url(repo_path)
    repo["issues_count"] = get_github_issues_count(repo_path)
    
    return repo


def get_all_repos():
    """Scan git directory and get status for all repos."""
    repos = []
    
    if not GIT_DIR.exists():
        return repos
    
    for item in sorted(GIT_DIR.iterdir()):
        if item.is_dir() and not item.name.startswith("."):
            status = get_repo_status(item)
            if status:
                repos.append(status)
    
    return repos


@app.route("/")
def dashboard():
    repos = get_all_repos()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return render_template_string(HTML_TEMPLATE, repos=repos, timestamp=timestamp)


@app.route("/api/status")
def api_status():
    """JSON API endpoint for programmatic access."""
    repos = get_all_repos()
    return jsonify({
        "timestamp": datetime.now().isoformat(),
        "repos": repos
    })


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Project Status Dashboard")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", "-p", type=int, default=5050, help="Port to run on")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    args = parser.parse_args()
    
    print(f"🚀 Starting Project Status Dashboard on http://{args.host}:{args.port}")
    app.run(host=args.host, port=args.port, debug=args.debug)
