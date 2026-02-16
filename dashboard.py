#!/usr/bin/env python3
"""
Project Status Dashboard v2
Enhanced version with interactive git operations (sync/fetch), AJAX updates, and better UX.
"""

import http.server
import socketserver
import json
import subprocess
import os
import sys
import urllib.parse
import time
from datetime import datetime, timezone
from pathlib import Path

class ProjectDashboardHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        self.git_repos_path = Path.home() / "git"
        super().__init__(*args, **kwargs)

    def get_repo_info(self, repo_path):
        """Get comprehensive git repository information."""
        repo_name = repo_path.name
        try:
            os.chdir(repo_path)
            
            # Get current branch
            branch = subprocess.check_output(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                text=True, stderr=subprocess.DEVNULL
            ).strip()
            
            # Get status
            status_output = subprocess.check_output(
                ["git", "status", "--porcelain"],
                text=True, stderr=subprocess.DEVNULL
            )
            uncommitted = len([line for line in status_output.split('\n') if line.strip()])
            
            # Get ahead/behind info
            try:
                ahead_behind = subprocess.check_output(
                    ["git", "rev-list", "--left-right", "--count", f"{branch}...origin/{branch}"],
                    text=True, stderr=subprocess.DEVNULL
                ).strip().split()
                ahead = int(ahead_behind[0]) if len(ahead_behind) >= 1 else 0
                behind = int(ahead_behind[1]) if len(ahead_behind) >= 2 else 0
            except (subprocess.CalledProcessError, IndexError, ValueError):
                ahead, behind = 0, 0
            
            # Get last commit info
            try:
                last_commit = subprocess.check_output([
                    "git", "log", "-1", "--pretty=format:%h|%s|%an|%ar"
                ], text=True, stderr=subprocess.DEVNULL).strip().split('|')
                commit_hash = last_commit[0] if len(last_commit) > 0 else ""
                commit_message = last_commit[1] if len(last_commit) > 1 else ""
                commit_author = last_commit[2] if len(last_commit) > 2 else ""
                commit_time = last_commit[3] if len(last_commit) > 3 else ""
            except (subprocess.CalledProcessError, IndexError):
                commit_hash, commit_message, commit_author, commit_time = "", "", "", ""
            
            # Check if remote exists
            try:
                remote_url = subprocess.check_output(
                    ["git", "remote", "get-url", "origin"],
                    text=True, stderr=subprocess.DEVNULL
                ).strip()
                has_remote = True
                
                # Extract GitHub info for links
                github_info = None
                if "github.com" in remote_url:
                    if remote_url.startswith("git@"):
                        # git@github.com:user/repo.git -> user/repo
                        github_path = remote_url.split(":")[-1].replace(".git", "")
                    else:
                        # https://github.com/user/repo.git -> user/repo
                        github_path = "/".join(remote_url.split("/")[-2:]).replace(".git", "")
                    
                    github_info = {
                        "path": github_path,
                        "url": f"https://github.com/{github_path}"
                    }
                    
                    # Get open issues count (if gh is available)
                    try:
                        issues_output = subprocess.check_output([
                            "gh", "issue", "list", "--repo", github_path, "--state", "open", "--json", "number"
                        ], text=True, stderr=subprocess.DEVNULL)
                        issues_data = json.loads(issues_output)
                        github_info["open_issues"] = len(issues_data)
                    except (subprocess.CalledProcessError, json.JSONDecodeError, FileNotFoundError):
                        github_info["open_issues"] = None
            except subprocess.CalledProcessError:
                has_remote = False
                github_info = None
            
            # Check if repo is dirty or needs attention
            needs_attention = uncommitted > 0 or ahead > 0 or behind > 0
            
            return {
                "name": repo_name,
                "path": str(repo_path),
                "branch": branch,
                "uncommitted": uncommitted,
                "ahead": ahead,
                "behind": behind,
                "needs_attention": needs_attention,
                "has_remote": has_remote,
                "last_commit": {
                    "hash": commit_hash,
                    "message": commit_message,
                    "author": commit_author,
                    "time": commit_time
                },
                "github": github_info
            }
        
        except Exception as e:
            return {
                "name": repo_name,
                "path": str(repo_path),
                "error": str(e),
                "needs_attention": True
            }

    def get_all_repos(self):
        """Scan for all git repositories."""
        repos = []
        try:
            for item in self.git_repos_path.iterdir():
                if item.is_dir() and (item / ".git").exists():
                    repo_info = self.get_repo_info(item)
                    repos.append(repo_info)
        except FileNotFoundError:
            pass
        
        # Sort by needs_attention (true first), then by name
        repos.sort(key=lambda x: (not x.get("needs_attention", False), x.get("name", "")))
        return repos

    def perform_git_operation(self, repo_path, operation):
        """Perform git operation (fetch or pull) on a repository."""
        try:
            os.chdir(repo_path)
            
            if operation == "fetch":
                result = subprocess.run(
                    ["git", "fetch", "origin"],
                    capture_output=True, text=True, timeout=30
                )
                return {
                    "success": result.returncode == 0,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "operation": "fetch"
                }
            
            elif operation == "pull":
                # Check if working directory is clean
                status_result = subprocess.run(
                    ["git", "status", "--porcelain"],
                    capture_output=True, text=True
                )
                
                if status_result.stdout.strip():
                    return {
                        "success": False,
                        "error": "Working directory has uncommitted changes. Please commit or stash them first.",
                        "operation": "pull"
                    }
                
                result = subprocess.run(
                    ["git", "pull", "origin"],
                    capture_output=True, text=True, timeout=60
                )
                
                return {
                    "success": result.returncode == 0,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "operation": "pull"
                }
            
            else:
                return {"success": False, "error": f"Unknown operation: {operation}"}
        
        except subprocess.TimeoutExpired:
            return {"success": False, "error": f"Operation {operation} timed out"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def do_GET(self):
        """Handle GET requests."""
        parsed_path = urllib.parse.urlparse(self.path)
        path = parsed_path.path
        
        if path == "/" or path == "/index.html":
            self.serve_dashboard()
        elif path == "/api/repos":
            self.serve_repos_json()
        elif path.startswith("/api/repo/") and "/fetch" in path:
            repo_name = path.split("/")[3]
            self.handle_git_operation(repo_name, "fetch")
        else:
            self.send_error(404, "Not Found")

    def do_POST(self):
        """Handle POST requests for git operations."""
        parsed_path = urllib.parse.urlparse(self.path)
        path = parsed_path.path
        
        if path.startswith("/api/repo/") and "/pull" in path:
            repo_name = path.split("/")[3]
            self.handle_git_operation(repo_name, "pull")
        else:
            self.send_error(404, "Not Found")

    def handle_git_operation(self, repo_name, operation):
        """Handle git fetch/pull operations."""
        repo_path = self.git_repos_path / repo_name
        
        if not repo_path.exists() or not (repo_path / ".git").exists():
            self.send_json_response({"success": False, "error": "Repository not found"})
            return
        
        result = self.perform_git_operation(str(repo_path), operation)
        
        # Get updated repo info
        if result["success"]:
            updated_info = self.get_repo_info(repo_path)
            result["repo_info"] = updated_info
        
        self.send_json_response(result)

    def serve_repos_json(self):
        """Serve repository data as JSON."""
        repos = self.get_all_repos()
        self.send_json_response({
            "repos": repos,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total": len(repos),
            "needs_attention": len([r for r in repos if r.get("needs_attention", False)])
        })

    def send_json_response(self, data):
        """Send JSON response."""
        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, indent=2).encode())

    def serve_dashboard(self):
        """Serve the main dashboard HTML."""
        html = self.get_dashboard_html()
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(html.encode())

    def get_dashboard_html(self):
        """Generate the dashboard HTML with enhanced interactivity."""
        return '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Project Status Dashboard v2</title>
    <style>
        body {
            font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
            margin: 0;
            padding: 20px;
            background: #0d1117;
            color: #c9d1d9;
            line-height: 1.6;
        }
        
        .header {
            text-align: center;
            margin-bottom: 30px;
            border-bottom: 2px solid #21262d;
            padding-bottom: 20px;
        }
        
        .header h1 {
            color: #58a6ff;
            margin: 0;
            font-size: 2.2em;
        }
        
        .stats {
            display: flex;
            justify-content: center;
            gap: 30px;
            margin: 20px 0;
            flex-wrap: wrap;
        }
        
        .stat {
            text-align: center;
            padding: 15px 25px;
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 8px;
        }
        
        .stat-value {
            font-size: 2em;
            font-weight: bold;
            margin: 0;
        }
        
        .stat-label {
            font-size: 0.9em;
            color: #8b949e;
            margin: 5px 0 0 0;
        }
        
        .controls {
            text-align: center;
            margin: 20px 0;
        }
        
        .btn {
            background: #238636;
            color: white;
            border: none;
            padding: 10px 20px;
            margin: 0 5px;
            border-radius: 6px;
            cursor: pointer;
            font-family: inherit;
            font-size: 14px;
            transition: background 0.2s;
        }
        
        .btn:hover {
            background: #2ea043;
        }
        
        .btn:disabled {
            background: #484f58;
            cursor: not-allowed;
        }
        
        .btn-secondary {
            background: #373e47;
        }
        
        .btn-secondary:hover {
            background: #444c56;
        }
        
        .btn-danger {
            background: #da3633;
        }
        
        .btn-danger:hover {
            background: #f85149;
        }
        
        .repos-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 20px;
            margin-top: 30px;
        }
        
        .repo-card {
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 8px;
            padding: 20px;
            transition: border-color 0.2s, background 0.2s;
        }
        
        .repo-card.needs-attention {
            border-left: 4px solid #f85149;
        }
        
        .repo-card.clean {
            border-left: 4px solid #238636;
        }
        
        .repo-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
        }
        
        .repo-name {
            font-size: 1.3em;
            font-weight: bold;
            margin: 0;
            color: #58a6ff;
        }
        
        .repo-actions {
            display: flex;
            gap: 8px;
        }
        
        .btn-small {
            padding: 6px 12px;
            font-size: 12px;
            min-width: 60px;
        }
        
        .repo-info {
            margin: 10px 0;
        }
        
        .repo-info div {
            margin: 5px 0;
        }
        
        .branch {
            color: #a5a5a5;
        }
        
        .status-item {
            display: inline-block;
            margin-right: 15px;
            padding: 3px 8px;
            border-radius: 4px;
            font-size: 0.9em;
        }
        
        .uncommitted {
            background: #533516;
            color: #f0ad4e;
        }
        
        .ahead {
            background: #0f5132;
            color: #75b798;
        }
        
        .behind {
            background: #58151c;
            color: #f47c7c;
        }
        
        .clean {
            background: #0f5132;
            color: #75b798;
        }
        
        .last-commit {
            margin-top: 15px;
            padding-top: 15px;
            border-top: 1px solid #30363d;
            font-size: 0.9em;
            color: #8b949e;
        }
        
        .commit-hash {
            font-family: monospace;
            background: #21262d;
            padding: 2px 6px;
            border-radius: 4px;
        }
        
        .github-link {
            color: #58a6ff;
            text-decoration: none;
            margin-left: 10px;
        }
        
        .github-link:hover {
            text-decoration: underline;
        }
        
        .open-issues {
            color: #f85149;
            font-weight: bold;
        }
        
        .loading {
            text-align: center;
            padding: 50px;
            color: #8b949e;
        }
        
        .error {
            background: #58151c;
            color: #f85149;
            padding: 15px;
            border-radius: 6px;
            margin: 20px 0;
        }
        
        .success {
            background: #0f5132;
            color: #75b798;
            padding: 15px;
            border-radius: 6px;
            margin: 20px 0;
        }
        
        .operation-output {
            background: #21262d;
            border: 1px solid #30363d;
            border-radius: 6px;
            padding: 12px;
            margin: 10px 0;
            font-family: monospace;
            font-size: 0.85em;
            white-space: pre-wrap;
            max-height: 200px;
            overflow-y: auto;
        }
        
        .timestamp {
            text-align: center;
            color: #8b949e;
            font-size: 0.9em;
            margin-top: 30px;
        }
        
        /* Modal styles */
        .modal {
            display: none;
            position: fixed;
            z-index: 1000;
            left: 0;
            top: 0;
            width: 100%;
            height: 100%;
            background-color: rgba(0,0,0,0.8);
        }
        
        .modal-content {
            background-color: #161b22;
            margin: 5% auto;
            padding: 30px;
            border: 1px solid #30363d;
            border-radius: 8px;
            width: 90%;
            max-width: 600px;
        }
        
        .modal h3 {
            margin-top: 0;
            color: #58a6ff;
        }
        
        .modal-buttons {
            text-align: right;
            margin-top: 20px;
        }
        
        @media (max-width: 768px) {
            .repos-grid {
                grid-template-columns: 1fr;
            }
            
            .stats {
                flex-direction: column;
                align-items: center;
                gap: 15px;
            }
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🔧 Project Status Dashboard v2</h1>
        <div class="stats" id="stats">
            <div class="stat">
                <div class="stat-value" id="total-repos">-</div>
                <div class="stat-label">Total Repositories</div>
            </div>
            <div class="stat">
                <div class="stat-value" id="needs-attention">-</div>
                <div class="stat-label">Need Attention</div>
            </div>
        </div>
        <div class="controls">
            <button class="btn" onclick="refreshAll()" id="refresh-btn">🔄 Refresh All</button>
            <button class="btn btn-secondary" onclick="toggleAutoRefresh()" id="auto-refresh-btn">⏰ Auto-Refresh: ON</button>
        </div>
    </div>

    <div id="repos-container" class="repos-grid">
        <div class="loading">Loading repositories...</div>
    </div>

    <div class="timestamp" id="timestamp"></div>

    <!-- Confirmation Modal -->
    <div id="confirmModal" class="modal">
        <div class="modal-content">
            <h3 id="modal-title">Confirm Action</h3>
            <p id="modal-message"></p>
            <div id="modal-details"></div>
            <div class="modal-buttons">
                <button class="btn btn-secondary" onclick="closeModal()">Cancel</button>
                <button class="btn btn-danger" onclick="confirmAction()" id="confirm-btn">Proceed</button>
            </div>
        </div>
    </div>

    <script>
        let autoRefreshInterval;
        let autoRefreshEnabled = true;
        let pendingAction = null;

        async function fetchRepos() {
            try {
                const response = await fetch('/api/repos');
                const data = await response.json();
                return data;
            } catch (error) {
                console.error('Failed to fetch repos:', error);
                return null;
            }
        }

        async function performGitOperation(repoName, operation) {
            const url = `/api/repo/${repoName}/${operation}`;
            const method = operation === 'pull' ? 'POST' : 'GET';
            
            try {
                const response = await fetch(url, { method });
                return await response.json();
            } catch (error) {
                return { success: false, error: error.message };
            }
        }

        function showConfirmationModal(title, message, details, action) {
            document.getElementById('modal-title').textContent = title;
            document.getElementById('modal-message').textContent = message;
            document.getElementById('modal-details').innerHTML = details || '';
            document.getElementById('confirmModal').style.display = 'block';
            pendingAction = action;
        }

        function closeModal() {
            document.getElementById('confirmModal').style.display = 'none';
            pendingAction = null;
        }

        async function confirmAction() {
            if (pendingAction) {
                closeModal();
                await pendingAction();
            }
        }

        function updateRepoCard(repo, result) {
            const card = document.querySelector(`[data-repo="${repo}"]`);
            if (!card) return;
            
            const actionsDiv = card.querySelector('.repo-actions');
            
            if (result.success) {
                // Show success message
                const successDiv = document.createElement('div');
                successDiv.className = 'success';
                successDiv.textContent = `✅ ${result.operation} completed successfully`;
                
                if (result.stdout) {
                    const outputDiv = document.createElement('div');
                    outputDiv.className = 'operation-output';
                    outputDiv.textContent = result.stdout;
                    successDiv.appendChild(outputDiv);
                }
                
                card.appendChild(successDiv);
                setTimeout(() => successDiv.remove(), 5000);
                
                // Update repo info if available
                if (result.repo_info) {
                    location.reload(); // Simple refresh for now
                }
            } else {
                // Show error message
                const errorDiv = document.createElement('div');
                errorDiv.className = 'error';
                errorDiv.textContent = `❌ ${result.operation || 'Operation'} failed: ${result.error}`;
                
                if (result.stderr) {
                    const outputDiv = document.createElement('div');
                    outputDiv.className = 'operation-output';
                    outputDiv.textContent = result.stderr;
                    errorDiv.appendChild(outputDiv);
                }
                
                card.appendChild(errorDiv);
                setTimeout(() => errorDiv.remove(), 8000);
            }
            
            // Re-enable buttons
            actionsDiv.querySelectorAll('button').forEach(btn => {
                btn.disabled = false;
                btn.textContent = btn.textContent.replace('...', '');
            });
        }

        async function fetchRepo(repoName) {
            const card = document.querySelector(`[data-repo="${repoName}"]`);
            const btn = card.querySelector('.fetch-btn');
            
            btn.disabled = true;
            btn.textContent = '📡 Fetching...';
            
            const result = await performGitOperation(repoName, 'fetch');
            updateRepoCard(repoName, result);
        }

        async function pullRepo(repoName, repoInfo) {
            const hasUncommitted = repoInfo.uncommitted > 0;
            const isBehind = repoInfo.behind > 0;
            
            if (!isBehind) {
                alert(`Repository "${repoName}" is already up to date.`);
                return;
            }
            
            let warningDetails = '';
            if (hasUncommitted) {
                warningDetails = '<div class="error">⚠️ This repository has uncommitted changes. The pull will fail.</div>';
            }
            
            const details = `
                <div style="margin: 15px 0;">
                    <strong>Repository:</strong> ${repoName}<br>
                    <strong>Current Branch:</strong> ${repoInfo.branch}<br>
                    <strong>Behind by:</strong> ${repoInfo.behind} commit(s)<br>
                    <strong>Uncommitted changes:</strong> ${repoInfo.uncommitted}
                </div>
                ${warningDetails}
            `;
            
            showConfirmationModal(
                'Confirm Git Pull',
                `Are you sure you want to pull the latest changes for "${repoName}"?`,
                details,
                async () => {
                    const card = document.querySelector(`[data-repo="${repoName}"]`);
                    const btn = card.querySelector('.pull-btn');
                    
                    btn.disabled = true;
                    btn.textContent = '⬇️ Pulling...';
                    
                    const result = await performGitOperation(repoName, 'pull');
                    updateRepoCard(repoName, result);
                }
            );
        }

        function renderRepos(data) {
            if (!data || !data.repos) return;
            
            const container = document.getElementById('repos-container');
            
            if (data.repos.length === 0) {
                container.innerHTML = '<div class="loading">No git repositories found in ~/git/</div>';
                return;
            }
            
            const html = data.repos.map(repo => {
                if (repo.error) {
                    return `
                        <div class="repo-card needs-attention" data-repo="${repo.name}">
                            <div class="repo-header">
                                <h3 class="repo-name">❌ ${repo.name}</h3>
                            </div>
                            <div class="error">Error: ${repo.error}</div>
                        </div>
                    `;
                }
                
                const statusItems = [];
                if (repo.uncommitted > 0) {
                    statusItems.push(`<span class="status-item uncommitted">📝 ${repo.uncommitted} uncommitted</span>`);
                }
                if (repo.ahead > 0) {
                    statusItems.push(`<span class="status-item ahead">⬆️ ${repo.ahead} ahead</span>`);
                }
                if (repo.behind > 0) {
                    statusItems.push(`<span class="status-item behind">⬇️ ${repo.behind} behind</span>`);
                }
                if (statusItems.length === 0) {
                    statusItems.push(`<span class="status-item clean">✅ Clean</span>`);
                }
                
                const githubLink = repo.github ? 
                    `<a href="${repo.github.url}" target="_blank" class="github-link" title="Open on GitHub">🔗 GitHub</a>
                     ${repo.github.open_issues !== null ? `<span class="open-issues">(${repo.github.open_issues} open issues)</span>` : ''}` : '';
                
                const lastCommit = repo.last_commit ? `
                    <div class="last-commit">
                        <strong>Last commit:</strong> 
                        <span class="commit-hash">${repo.last_commit.hash}</span>
                        ${repo.last_commit.message} 
                        <br><small>by ${repo.last_commit.author} • ${repo.last_commit.time}</small>
                    </div>
                ` : '';
                
                const canPull = repo.has_remote && repo.behind > 0;
                const canFetch = repo.has_remote;
                
                return `
                    <div class="repo-card ${repo.needs_attention ? 'needs-attention' : 'clean'}" data-repo="${repo.name}">
                        <div class="repo-header">
                            <h3 class="repo-name">${repo.needs_attention ? '⚠️' : '✅'} ${repo.name}</h3>
                            <div class="repo-actions">
                                ${canFetch ? `<button class="btn btn-small btn-secondary fetch-btn" onclick="fetchRepo('${repo.name}')" title="Fetch latest refs from remote">📡 Fetch</button>` : ''}
                                ${canPull ? `<button class="btn btn-small pull-btn" onclick="pullRepo('${repo.name}', ${JSON.stringify(repo).replace(/'/g, "\\'").replace(/"/g, "&quot;")})" title="Pull latest changes">⬇️ Pull</button>` : ''}
                            </div>
                        </div>
                        <div class="repo-info">
                            <div><strong>Branch:</strong> <span class="branch">${repo.branch}</span> ${githubLink}</div>
                            <div><strong>Status:</strong> ${statusItems.join('')}</div>
                        </div>
                        ${lastCommit}
                    </div>
                `;
            }).join('');
            
            container.innerHTML = html;
            
            // Update stats
            document.getElementById('total-repos').textContent = data.total;
            document.getElementById('needs-attention').textContent = data.needs_attention;
            document.getElementById('timestamp').textContent = `Last updated: ${new Date(data.timestamp).toLocaleString()}`;
        }

        async function refreshAll() {
            const btn = document.getElementById('refresh-btn');
            btn.disabled = true;
            btn.textContent = '🔄 Refreshing...';
            
            const data = await fetchRepos();
            if (data) {
                renderRepos(data);
            } else {
                document.getElementById('repos-container').innerHTML = '<div class="error">Failed to load repository data</div>';
            }
            
            btn.disabled = false;
            btn.textContent = '🔄 Refresh All';
        }

        function toggleAutoRefresh() {
            const btn = document.getElementById('auto-refresh-btn');
            
            if (autoRefreshEnabled) {
                clearInterval(autoRefreshInterval);
                autoRefreshEnabled = false;
                btn.textContent = '⏰ Auto-Refresh: OFF';
                btn.className = 'btn btn-secondary';
            } else {
                autoRefreshInterval = setInterval(refreshAll, 60000);
                autoRefreshEnabled = true;
                btn.textContent = '⏰ Auto-Refresh: ON';
                btn.className = 'btn btn-secondary';
            }
        }

        // Close modal when clicking outside
        window.onclick = function(event) {
            const modal = document.getElementById('confirmModal');
            if (event.target === modal) {
                closeModal();
            }
        }

        // Initialize dashboard
        document.addEventListener('DOMContentLoaded', async () => {
            await refreshAll();
            
            // Start auto-refresh
            autoRefreshInterval = setInterval(refreshAll, 60000);
        });
    </script>
</body>
</html>'''

def main():
    PORT = 8766  # Different from v1 to avoid conflicts
    
    print(f"🔧 Project Status Dashboard v2")
    print(f"Starting server on http://localhost:{PORT}")
    print(f"Scanning repositories in: {Path.home() / 'git'}")
    print("\nFeatures:")
    print("• Interactive git fetch/pull operations")
    print("• Confirmation dialogs for safety")
    print("• Real-time status updates")
    print("• Auto-refresh (60s intervals)")
    print("\nPress Ctrl+C to stop")
    
    try:
        with socketserver.TCPServer(("", PORT), ProjectDashboardHandler) as httpd:
            httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n\nShutting down dashboard...")
        sys.exit(0)
    except OSError as e:
        if "Address already in use" in str(e):
            print(f"\n❌ Port {PORT} is already in use. Try a different port.")
            sys.exit(1)
        else:
            raise

if __name__ == "__main__":
    main()