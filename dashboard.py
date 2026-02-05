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
from concurrent.futures import ThreadPoolExecutor, as_completed
from flask import Flask, render_template_string, request, jsonify

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
        
        .sort-controls {
            display: flex;
            gap: 0.5rem;
        }
        
        .sort-btn {
            background: var(--bg-tertiary);
            border: 1px solid var(--border);
            color: var(--text-secondary);
            padding: 0.4rem 0.8rem;
            border-radius: 6px;
            font-size: 0.8rem;
            cursor: pointer;
            text-decoration: none;
            transition: all 0.2s;
        }
        
        .sort-btn:hover {
            border-color: var(--accent-blue);
            color: var(--text-primary);
        }
        
        .sort-btn.active {
            background: var(--accent-blue);
            border-color: var(--accent-blue);
            color: var(--bg-primary);
        }
        
        .toggle-label {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            font-size: 0.8rem;
            color: var(--text-secondary);
            cursor: pointer;
        }
        
        .toggle-label input {
            cursor: pointer;
        }
        
        .card.clean {
            /* for JS filtering */
        }
        
        .hide-clean .card.clean {
            display: none;
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
        
        .card-actions {
            display: flex;
            gap: 0.5rem;
            margin-top: 0.75rem;
            padding-top: 0.75rem;
            border-top: 1px solid var(--border);
        }
        
        .action-btn {
            flex: 1;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: 0.35rem;
            background: var(--bg-tertiary);
            border: 1px solid var(--border);
            color: var(--text-secondary);
            padding: 0.5rem 0.75rem;
            border-radius: 6px;
            font-size: 0.8rem;
            cursor: pointer;
            transition: all 0.2s;
        }
        
        .action-btn:hover:not(:disabled) {
            border-color: var(--accent-blue);
            color: var(--text-primary);
        }
        
        .action-btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }
        
        .action-btn.loading {
            position: relative;
            color: transparent;
        }
        
        .action-btn.loading::after {
            content: "";
            position: absolute;
            width: 14px;
            height: 14px;
            border: 2px solid var(--text-secondary);
            border-top-color: transparent;
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
        }
        
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
        
        .action-btn.sync-btn:hover:not(:disabled) {
            border-color: var(--accent-purple);
            color: var(--accent-purple);
        }
        
        .action-btn.fetch-btn:hover:not(:disabled) {
            border-color: var(--accent-blue);
            color: var(--accent-blue);
        }
        
        .feedback {
            margin-top: 0.5rem;
            padding: 0.5rem 0.75rem;
            border-radius: 6px;
            font-size: 0.8rem;
            display: none;
        }
        
        .feedback.success {
            display: block;
            background: rgba(63, 185, 80, 0.15);
            border: 1px solid var(--accent-green);
            color: var(--accent-green);
        }
        
        .feedback.error {
            display: block;
            background: rgba(248, 81, 73, 0.15);
            border: 1px solid var(--accent-red);
            color: var(--accent-red);
        }
        
        .confirm-dialog {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0, 0, 0, 0.7);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 1000;
        }
        
        .confirm-box {
            background: var(--bg-secondary);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 1.5rem;
            max-width: 400px;
            width: 90%;
        }
        
        .confirm-box h3 {
            margin-bottom: 0.75rem;
            color: var(--text-primary);
        }
        
        .confirm-box p {
            color: var(--text-secondary);
            margin-bottom: 1.25rem;
            font-size: 0.9rem;
        }
        
        .confirm-actions {
            display: flex;
            gap: 0.75rem;
            justify-content: flex-end;
        }
        
        .confirm-btn {
            padding: 0.5rem 1rem;
            border-radius: 6px;
            border: 1px solid var(--border);
            cursor: pointer;
            font-size: 0.85rem;
            transition: all 0.2s;
        }
        
        .confirm-btn.cancel {
            background: var(--bg-tertiary);
            color: var(--text-secondary);
        }
        
        .confirm-btn.cancel:hover {
            color: var(--text-primary);
            border-color: var(--text-secondary);
        }
        
        .confirm-btn.confirm {
            background: var(--accent-purple);
            border-color: var(--accent-purple);
            color: white;
        }
        
        .confirm-btn.confirm:hover {
            background: #8b5cf6;
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
            <div class="sort-controls">
                <a href="?sort=recent" class="sort-btn {{ 'active' if sort_by == 'recent' else '' }}">Recent</a>
                <a href="?sort=alpha" class="sort-btn {{ 'active' if sort_by == 'alpha' else '' }}">A-Z</a>
                <label class="toggle-label">
                    <input type="checkbox" id="hideClean" onchange="toggleClean()"> Hide clean
                </label>
                <span class="timestamp">Updated: {{ timestamp }}</span>
            </div>
        </header>
        <div class="grid" id="repoGrid">
            {% for repo in repos %}
            <div class="card{% if repo.changes_count == 0 and repo.ahead == 0 and repo.behind == 0 %} clean{% endif %}">
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
                
                <div class="card-actions">
                    <button class="action-btn fetch-btn" onclick="fetchRepo('{{ repo.name }}')" title="Fetch remote changes">
                        🔄 Fetch
                    </button>
                    <button class="action-btn sync-btn" onclick="confirmSync('{{ repo.name }}')" title="Pull remote changes">
                        ⬇️ Sync
                    </button>
                </div>
                <div class="feedback" id="feedback-{{ repo.name }}"></div>
                {% endif %}
            </div>
            {% endfor %}
        </div>
    </div>
    <script>
        function toggleClean() {
            const grid = document.getElementById('repoGrid');
            const checkbox = document.getElementById('hideClean');
            if (checkbox.checked) {
                grid.classList.add('hide-clean');
                localStorage.setItem('hideClean', 'true');
            } else {
                grid.classList.remove('hide-clean');
                localStorage.setItem('hideClean', 'false');
            }
        }
        
        // Restore preference on load
        document.addEventListener('DOMContentLoaded', function() {
            if (localStorage.getItem('hideClean') === 'true') {
                document.getElementById('hideClean').checked = true;
                document.getElementById('repoGrid').classList.add('hide-clean');
            }
        });
        
        function showFeedback(repo, message, isError) {
            const fb = document.getElementById('feedback-' + repo);
            if (fb) {
                fb.textContent = message;
                fb.className = 'feedback ' + (isError ? 'error' : 'success');
                // Auto-hide after 5s
                setTimeout(() => {
                    fb.className = 'feedback';
                }, 5000);
            }
        }
        
        function setButtonLoading(btn, loading) {
            if (loading) {
                btn.classList.add('loading');
                btn.disabled = true;
            } else {
                btn.classList.remove('loading');
                btn.disabled = false;
            }
        }
        
        async function fetchRepo(repo) {
            const btn = event.target.closest('.fetch-btn');
            setButtonLoading(btn, true);
            
            try {
                const response = await fetch('/api/fetch/' + encodeURIComponent(repo), {
                    method: 'POST'
                });
                const data = await response.json();
                
                if (data.success) {
                    let msg = '✓ Fetched successfully';
                    if (data.ahead !== undefined || data.behind !== undefined) {
                        const parts = [];
                        if (data.ahead > 0) parts.push('↑' + data.ahead + ' ahead');
                        if (data.behind > 0) parts.push('↓' + data.behind + ' behind');
                        if (parts.length > 0) {
                            msg += ' (' + parts.join(', ') + ')';
                        } else {
                            msg += ' (in sync)';
                        }
                    }
                    showFeedback(repo, msg, false);
                    
                    // Update the sync stat in the card
                    updateSyncStat(repo, data.ahead, data.behind);
                } else {
                    showFeedback(repo, '✗ ' + (data.error || 'Fetch failed'), true);
                }
            } catch (err) {
                showFeedback(repo, '✗ Network error', true);
            } finally {
                setButtonLoading(btn, false);
            }
        }
        
        function updateSyncStat(repo, ahead, behind) {
            // Find the card for this repo and update the sync stat
            const cards = document.querySelectorAll('.card');
            for (const card of cards) {
                const nameEl = card.querySelector('.repo-name');
                if (nameEl && nameEl.textContent === repo) {
                    const stats = card.querySelectorAll('.stat');
                    for (const stat of stats) {
                        const label = stat.querySelector('.stat-label');
                        if (label && label.textContent === 'Sync') {
                            const valueEl = stat.querySelector('.stat-value');
                            if (valueEl) {
                                let className = 'stat-value ';
                                let text = '';
                                if (ahead > 0 && behind > 0) {
                                    className += 'dirty';
                                    text = '↑' + ahead + ' ↓' + behind;
                                } else if (ahead > 0) {
                                    className += 'ahead';
                                    text = '↑' + ahead;
                                } else if (behind > 0) {
                                    className += 'behind';
                                    text = '↓' + behind;
                                } else {
                                    className += 'synced';
                                    text = '✓ Synced';
                                }
                                valueEl.className = className;
                                valueEl.textContent = text;
                            }
                            break;
                        }
                    }
                    break;
                }
            }
        }
        
        function confirmSync(repo) {
            const dialog = document.createElement('div');
            dialog.className = 'confirm-dialog';
            dialog.innerHTML = `
                <div class="confirm-box">
                    <h3>⬇️ Sync Repository</h3>
                    <p>This will run <code>git pull</code> on <strong>${repo}</strong>. Make sure you don't have conflicting local changes.</p>
                    <div class="confirm-actions">
                        <button class="confirm-btn cancel" onclick="this.closest('.confirm-dialog').remove()">Cancel</button>
                        <button class="confirm-btn confirm" onclick="doSync('${repo}', this)">Pull Changes</button>
                    </div>
                </div>
            `;
            document.body.appendChild(dialog);
            
            // Close on backdrop click
            dialog.addEventListener('click', (e) => {
                if (e.target === dialog) dialog.remove();
            });
        }
        
        async function doSync(repo, confirmBtn) {
            const dialog = confirmBtn.closest('.confirm-dialog');
            confirmBtn.disabled = true;
            confirmBtn.textContent = 'Pulling...';
            
            try {
                const response = await fetch('/api/pull/' + encodeURIComponent(repo), {
                    method: 'POST'
                });
                const data = await response.json();
                
                dialog.remove();
                
                if (data.success) {
                    let msg = '✓ Pull successful';
                    if (data.message) {
                        msg += ': ' + data.message;
                    }
                    showFeedback(repo, msg, false);
                    
                    // Update sync stat to show we're in sync now
                    if (data.ahead !== undefined) {
                        updateSyncStat(repo, data.ahead, data.behind || 0);
                    }
                } else {
                    showFeedback(repo, '✗ ' + (data.error || 'Pull failed'), true);
                }
            } catch (err) {
                dialog.remove();
                showFeedback(repo, '✗ Network error', true);
            }
        }
    </script>
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
        "last_timestamp": 0,
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
    
    # Ahead/behind (uses cached remote tracking - no fetch for speed)
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
            # Store raw timestamp for sorting
            try:
                dt = datetime.fromisoformat(parts[2].replace("Z", "+00:00"))
                repo["last_timestamp"] = dt.timestamp()
            except Exception:
                pass
    
    # GitHub URL and issues
    repo["github_url"] = get_github_url(repo_path)
    repo["issues_count"] = get_github_issues_count(repo_path)
    
    return repo


def get_all_repos(sort_by="alpha"):
    """Scan git directory and get status for all repos (parallel)."""
    repos = []
    
    if not GIT_DIR.exists():
        return repos
    
    # Collect all repo paths first
    repo_paths = [
        item for item in sorted(GIT_DIR.iterdir())
        if item.is_dir() and not item.name.startswith(".")
    ]
    
    # Process repos in parallel (max 10 workers to avoid overwhelming git/network)
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(get_repo_status, path): path for path in repo_paths}
        for future in as_completed(futures):
            status = future.result()
            if status:
                repos.append(status)
    
    # Sort based on preference
    if sort_by == "recent":
        repos.sort(key=lambda r: r.get("last_timestamp", 0), reverse=True)
    else:
        repos.sort(key=lambda r: r["name"].lower())
    return repos


@app.route("/")
def dashboard():
    sort_by = request.args.get("sort", "recent")  # default to recent
    repos = get_all_repos(sort_by=sort_by)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return render_template_string(HTML_TEMPLATE, repos=repos, timestamp=timestamp, sort_by=sort_by)


@app.route("/api/status")
def api_status():
    """JSON API endpoint for programmatic access."""
    repos = get_all_repos()
    return jsonify({
        "timestamp": datetime.now().isoformat(),
        "repos": repos
    })


def validate_repo_name(name):
    """Validate repo name to prevent directory traversal."""
    # Only allow alphanumeric, dash, underscore, dot
    import re
    if not re.match(r'^[\w\-\.]+$', name):
        return False
    if '..' in name or name.startswith('.'):
        return False
    return True


@app.route("/api/fetch/<repo>", methods=["POST"])
def api_fetch(repo):
    """Fetch remote changes for a repo (git fetch)."""
    if not validate_repo_name(repo):
        return jsonify({"success": False, "error": "Invalid repository name"}), 400
    
    repo_path = GIT_DIR / repo
    if not repo_path.exists() or not (repo_path / ".git").exists():
        return jsonify({"success": False, "error": "Repository not found"}), 404
    
    # Run git fetch
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_path), "fetch", "--all"],
            capture_output=True,
            text=True,
            timeout=60
        )
        if result.returncode != 0:
            return jsonify({
                "success": False,
                "error": result.stderr.strip() or "Fetch failed"
            })
    except subprocess.TimeoutExpired:
        return jsonify({"success": False, "error": "Fetch timed out"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})
    
    # Get updated ahead/behind status
    ahead, behind = 0, 0
    tracking = run_git(repo_path, "rev-parse", "--abbrev-ref", "@{upstream}")
    if tracking:
        ahead_behind = run_git(repo_path, "rev-list", "--left-right", "--count", "HEAD...@{upstream}")
        if ahead_behind:
            parts = ahead_behind.split()
            if len(parts) == 2:
                ahead = int(parts[0])
                behind = int(parts[1])
    
    return jsonify({
        "success": True,
        "ahead": ahead,
        "behind": behind
    })


@app.route("/api/pull/<repo>", methods=["POST"])
def api_pull(repo):
    """Pull remote changes for a repo (git pull)."""
    if not validate_repo_name(repo):
        return jsonify({"success": False, "error": "Invalid repository name"}), 400
    
    repo_path = GIT_DIR / repo
    if not repo_path.exists() or not (repo_path / ".git").exists():
        return jsonify({"success": False, "error": "Repository not found"}), 404
    
    # Run git pull
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_path), "pull"],
            capture_output=True,
            text=True,
            timeout=120
        )
        if result.returncode != 0:
            return jsonify({
                "success": False,
                "error": result.stderr.strip() or "Pull failed"
            })
    except subprocess.TimeoutExpired:
        return jsonify({"success": False, "error": "Pull timed out"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})
    
    # Parse output for useful message
    output = result.stdout.strip()
    message = ""
    if "Already up to date" in output:
        message = "Already up to date"
    elif "files changed" in output or "insertions" in output:
        # Extract summary line
        lines = output.split('\n')
        for line in lines:
            if "files changed" in line or "file changed" in line:
                message = line.strip()
                break
    
    # Get updated ahead/behind status
    ahead, behind = 0, 0
    tracking = run_git(repo_path, "rev-parse", "--abbrev-ref", "@{upstream}")
    if tracking:
        ahead_behind = run_git(repo_path, "rev-list", "--left-right", "--count", "HEAD...@{upstream}")
        if ahead_behind:
            parts = ahead_behind.split()
            if len(parts) == 2:
                ahead = int(parts[0])
                behind = int(parts[1])
    
    return jsonify({
        "success": True,
        "message": message,
        "ahead": ahead,
        "behind": behind
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
