#!/usr/bin/env python3
"""
Project Status Dashboard v2
Enhanced interactive dashboard with git operations

Usage: python dashboard.py [--port 8766] [--git-dir ~/git]
"""

import os
import sys
import json
import subprocess
import html
import urllib.parse
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
import argparse
import threading
import time

class RepoInfo:
    def __init__(self, path):
        self.path = Path(path)
        self.name = self.path.name
        self.status = self._get_status()
        
    def _get_status(self):
        """Get comprehensive repo status"""
        if not (self.path / '.git').exists():
            return {
                'error': 'Not a git repository',
                'is_repo': False
            }
            
        status = {
            'is_repo': True,
            'path': str(self.path),
            'name': self.name
        }
        
        try:
            os.chdir(self.path)
            
            # Current branch
            result = subprocess.run(['git', 'branch', '--show-current'], 
                                 capture_output=True, text=True, timeout=5)
            status['branch'] = result.stdout.strip() if result.returncode == 0 else 'unknown'
            
            # Uncommitted changes
            result = subprocess.run(['git', 'status', '--porcelain'], 
                                 capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                changes = result.stdout.strip().split('\n') if result.stdout.strip() else []
                status['uncommitted_count'] = len(changes)
                status['has_uncommitted'] = len(changes) > 0
                status['uncommitted_files'] = changes[:5]  # First 5 for preview
            else:
                status['uncommitted_count'] = 0
                status['has_uncommitted'] = False
                status['uncommitted_files'] = []
            
            # Remote tracking
            result = subprocess.run(['git', 'rev-parse', '--abbrev-ref', '@{upstream}'], 
                                 capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                upstream = result.stdout.strip()
                status['upstream'] = upstream
                
                # Fetch to get latest remote info (this is safe)
                subprocess.run(['git', 'fetch', '--dry-run'], 
                             capture_output=True, timeout=10)
                
                # Ahead/behind
                result = subprocess.run(['git', 'rev-list', '--left-right', '--count', f'HEAD...{upstream}'], 
                                     capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    counts = result.stdout.strip().split('\t')
                    status['ahead'] = int(counts[0]) if len(counts) > 0 else 0
                    status['behind'] = int(counts[1]) if len(counts) > 1 else 0
                else:
                    status['ahead'] = 0
                    status['behind'] = 0
            else:
                status['upstream'] = None
                status['ahead'] = 0
                status['behind'] = 0
            
            # Last commit
            result = subprocess.run(['git', 'log', '-1', '--format=%H|%s|%an|%ar'], 
                                 capture_output=True, text=True, timeout=5)
            if result.returncode == 0 and result.stdout.strip():
                parts = result.stdout.strip().split('|')
                status['last_commit'] = {
                    'hash': parts[0][:8] if len(parts) > 0 else '',
                    'message': parts[1] if len(parts) > 1 else '',
                    'author': parts[2] if len(parts) > 2 else '',
                    'time': parts[3] if len(parts) > 3 else ''
                }
            else:
                status['last_commit'] = None
                
            # GitHub info (if gh CLI is available)
            try:
                result = subprocess.run(['gh', 'repo', 'view', '--json', 'url,openIssues'], 
                                     capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    gh_info = json.loads(result.stdout)
                    status['github_url'] = gh_info.get('url', '')
                    status['open_issues'] = gh_info.get('openIssues', {}).get('totalCount', 0)
            except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
                pass
                
        except subprocess.TimeoutExpired:
            status['error'] = 'Git command timed out'
        except Exception as e:
            status['error'] = str(e)
            
        return status

class DashboardHandler(BaseHTTPRequestHandler):
    def __init__(self, git_dir, *args, **kwargs):
        self.git_dir = Path(git_dir)
        super().__init__(*args, **kwargs)
    
    def do_GET(self):
        """Handle GET requests"""
        if self.path == '/':
            self._send_dashboard()
        elif self.path == '/api/repos':
            self._send_repos_json()
        elif self.path.startswith('/api/repo/') and self.path.endswith('/fetch'):
            # Safe operation - can be GET
            repo_name = self.path.split('/')[3]
            self._handle_fetch(repo_name)
        else:
            self._send_404()
    
    def do_POST(self):
        """Handle POST requests"""
        if self.path.startswith('/api/repo/') and '/pull' in self.path:
            repo_name = self.path.split('/')[3]
            
            # Read POST body for confirmation
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length:
                post_data = self.rfile.read(content_length).decode('utf-8')
                try:
                    data = json.loads(post_data)
                    confirmed = data.get('confirmed', False)
                except json.JSONDecodeError:
                    confirmed = False
            else:
                confirmed = False
            
            self._handle_pull(repo_name, confirmed)
        else:
            self._send_404()
    
    def _send_dashboard(self):
        """Send the main dashboard HTML"""
        html_content = self._generate_html()
        self._send_response(200, html_content, 'text/html')
    
    def _send_repos_json(self):
        """Send repository information as JSON"""
        repos_data = self._get_repos_data()
        self._send_response(200, json.dumps(repos_data, indent=2), 'application/json')
    
    def _handle_fetch(self, repo_name):
        """Handle git fetch operation"""
        repo_path = self.git_dir / repo_name
        if not repo_path.exists():
            self._send_error_json(404, f"Repository {repo_name} not found")
            return
            
        try:
            os.chdir(repo_path)
            result = subprocess.run(['git', 'fetch'], 
                                 capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                # Get updated status
                repo = RepoInfo(repo_path)
                response = {
                    'success': True,
                    'message': 'Fetch completed successfully',
                    'output': result.stdout + result.stderr,
                    'repo_status': repo.status
                }
            else:
                response = {
                    'success': False,
                    'message': 'Fetch failed',
                    'output': result.stdout + result.stderr
                }
                
        except subprocess.TimeoutExpired:
            response = {
                'success': False,
                'message': 'Fetch timed out'
            }
        except Exception as e:
            response = {
                'success': False,
                'message': f'Error during fetch: {str(e)}'
            }
        
        self._send_response(200, json.dumps(response), 'application/json')
    
    def _handle_pull(self, repo_name, confirmed=False):
        """Handle git pull operation with safety checks"""
        repo_path = self.git_dir / repo_name
        if not repo_path.exists():
            self._send_error_json(404, f"Repository {repo_name} not found")
            return
        
        try:
            os.chdir(repo_path)
            repo = RepoInfo(repo_path)
            
            # Safety check: uncommitted changes
            if not confirmed and repo.status.get('has_uncommitted', False):
                response = {
                    'success': False,
                    'need_confirmation': True,
                    'message': f'Repository has {repo.status["uncommitted_count"]} uncommitted changes',
                    'details': {
                        'branch': repo.status.get('branch', 'unknown'),
                        'uncommitted_count': repo.status.get('uncommitted_count', 0),
                        'ahead': repo.status.get('ahead', 0),
                        'behind': repo.status.get('behind', 0)
                    },
                    'warning': 'Pull may fail or create merge conflicts. Confirm to continue.'
                }
                self._send_response(200, json.dumps(response), 'application/json')
                return
            
            # Perform the pull
            result = subprocess.run(['git', 'pull'], 
                                 capture_output=True, text=True, timeout=60)
            
            if result.returncode == 0:
                # Get updated status
                updated_repo = RepoInfo(repo_path)
                response = {
                    'success': True,
                    'message': 'Pull completed successfully',
                    'output': result.stdout + result.stderr,
                    'repo_status': updated_repo.status
                }
            else:
                response = {
                    'success': False,
                    'message': 'Pull failed',
                    'output': result.stdout + result.stderr
                }
                
        except subprocess.TimeoutExpired:
            response = {
                'success': False,
                'message': 'Pull timed out'
            }
        except Exception as e:
            response = {
                'success': False,
                'message': f'Error during pull: {str(e)}'
            }
        
        self._send_response(200, json.dumps(response), 'application/json')
    
    def _get_repos_data(self):
        """Scan git directory and get repository information"""
        repos = []
        
        if not self.git_dir.exists():
            return {'error': f'Git directory {self.git_dir} does not exist', 'repos': []}
        
        for item in sorted(self.git_dir.iterdir()):
            if item.is_dir() and not item.name.startswith('.'):
                try:
                    repo = RepoInfo(item)
                    repos.append(repo.status)
                except Exception as e:
                    repos.append({
                        'name': item.name,
                        'error': str(e),
                        'is_repo': False
                    })
        
        return {
            'scan_time': datetime.now(timezone.utc).isoformat(),
            'git_dir': str(self.git_dir),
            'total_repos': len([r for r in repos if r.get('is_repo', False)]),
            'repos': repos
        }
    
    def _generate_html(self):
        """Generate the dashboard HTML"""
        return '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Project Status Dashboard v2</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            margin: 0;
            padding: 20px;
            background: #0d1117;
            color: #e6edf3;
            line-height: 1.6;
        }
        
        .header {
            text-align: center;
            margin-bottom: 30px;
        }
        
        .header h1 {
            margin: 0;
            color: #7c3aed;
            font-size: 2.5em;
            font-weight: 700;
        }
        
        .header p {
            color: #8b949e;
            margin: 10px 0;
        }
        
        .controls {
            display: flex;
            justify-content: center;
            gap: 15px;
            margin-bottom: 30px;
            flex-wrap: wrap;
        }
        
        .btn {
            padding: 8px 16px;
            border: 1px solid #30363d;
            background: #21262d;
            color: #e6edf3;
            text-decoration: none;
            border-radius: 6px;
            cursor: pointer;
            font-size: 14px;
            transition: all 0.2s;
        }
        
        .btn:hover {
            background: #30363d;
            border-color: #8b949e;
        }
        
        .btn.primary {
            background: #238636;
            border-color: #238636;
        }
        
        .btn.primary:hover {
            background: #2ea043;
        }
        
        .btn.danger {
            background: #da3633;
            border-color: #da3633;
        }
        
        .btn.danger:hover {
            background: #f85149;
        }
        
        .btn:disabled {
            background: #161b22;
            color: #6e7681;
            cursor: not-allowed;
            opacity: 0.6;
        }
        
        .repos {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 20px;
            max-width: 1400px;
            margin: 0 auto;
        }
        
        .repo {
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 8px;
            padding: 20px;
            transition: border-color 0.2s;
        }
        
        .repo:hover {
            border-color: #8b949e;
        }
        
        .repo-header {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 15px;
            flex-wrap: wrap;
            gap: 10px;
        }
        
        .repo-name {
            font-size: 18px;
            font-weight: 600;
            color: #58a6ff;
            margin: 0;
        }
        
        .repo-actions {
            display: flex;
            gap: 8px;
        }
        
        .btn-sm {
            padding: 4px 8px;
            font-size: 12px;
            min-width: 50px;
        }
        
        .status-grid {
            display: grid;
            grid-template-columns: auto 1fr;
            gap: 8px 15px;
            margin-bottom: 15px;
        }
        
        .status-label {
            color: #8b949e;
            font-size: 13px;
        }
        
        .status-value {
            font-size: 13px;
        }
        
        .badge {
            display: inline-block;
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 500;
            margin-left: 5px;
        }
        
        .badge.clean { background: #1f6332; color: #7ee787; }
        .badge.dirty { background: #914d14; color: #ffab70; }
        .badge.ahead { background: #1158c7; color: #79c0ff; }
        .badge.behind { background: #ad5b00; color: #ffa657; }
        .badge.issues { background: #8a4d76; color: #f2cc60; }
        
        .commit-info {
            background: #0d1117;
            border: 1px solid #21262d;
            border-radius: 6px;
            padding: 10px;
            margin-top: 10px;
            font-size: 12px;
        }
        
        .commit-hash {
            color: #8b949e;
            font-family: 'SF Mono', Consolas, monospace;
        }
        
        .error {
            color: #f85149;
            background: #251b1b;
            padding: 10px;
            border-radius: 6px;
            border-left: 3px solid #f85149;
        }
        
        .loading {
            text-align: center;
            padding: 40px;
            color: #8b949e;
        }
        
        .success-message, .error-message {
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 12px 20px;
            border-radius: 6px;
            z-index: 1000;
            max-width: 400px;
            animation: slideIn 0.3s ease-out;
        }
        
        .success-message {
            background: #1f6332;
            color: #7ee787;
            border: 1px solid #238636;
        }
        
        .error-message {
            background: #461e20;
            color: #f85149;
            border: 1px solid #da3633;
        }
        
        @keyframes slideIn {
            from { transform: translateX(100%); opacity: 0; }
            to { transform: translateX(0); opacity: 1; }
        }
        
        .modal {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0, 0, 0, 0.8);
            z-index: 2000;
            align-items: center;
            justify-content: center;
        }
        
        .modal.show {
            display: flex;
        }
        
        .modal-content {
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 8px;
            padding: 24px;
            max-width: 500px;
            width: 90%;
        }
        
        .modal h3 {
            margin-top: 0;
            color: #f0ad4e;
        }
        
        .modal-actions {
            display: flex;
            gap: 10px;
            justify-content: flex-end;
            margin-top: 20px;
        }
        
        @media (max-width: 768px) {
            .repos {
                grid-template-columns: 1fr;
                gap: 15px;
            }
            
            .repo {
                padding: 15px;
            }
            
            .controls {
                flex-direction: column;
                align-items: center;
            }
            
            .repo-actions {
                width: 100%;
                justify-content: center;
            }
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🐱 Project Dashboard v2</h1>
        <p>Interactive Git Repository Status</p>
        <div id="last-update">Loading...</div>
    </div>
    
    <div class="controls">
        <button class="btn" onclick="refreshData()">🔄 Refresh</button>
        <button class="btn" id="auto-refresh-btn" onclick="toggleAutoRefresh()">⏸️ Pause Auto-refresh</button>
        <a class="btn" href="/api/repos" target="_blank">📋 JSON API</a>
    </div>
    
    <div id="repos-container" class="loading">
        Loading repositories...
    </div>
    
    <!-- Confirmation Modal -->
    <div id="confirmation-modal" class="modal">
        <div class="modal-content">
            <h3>⚠️ Confirm Git Pull</h3>
            <div id="modal-details"></div>
            <p id="modal-warning"></p>
            <div class="modal-actions">
                <button class="btn" onclick="closeModal()">Cancel</button>
                <button class="btn danger" id="confirm-pull-btn">Pull Anyway</button>
            </div>
        </div>
    </div>
    
    <script>
        let autoRefreshInterval;
        let autoRefreshEnabled = true;
        
        // Auto-refresh every 60 seconds
        function startAutoRefresh() {
            if (autoRefreshInterval) clearInterval(autoRefreshInterval);
            autoRefreshInterval = setInterval(refreshData, 60000);
        }
        
        function toggleAutoRefresh() {
            const btn = document.getElementById('auto-refresh-btn');
            if (autoRefreshEnabled) {
                clearInterval(autoRefreshInterval);
                btn.textContent = '▶️ Resume Auto-refresh';
                autoRefreshEnabled = false;
            } else {
                startAutoRefresh();
                btn.textContent = '⏸️ Pause Auto-refresh';
                autoRefreshEnabled = true;
            }
        }
        
        function refreshData() {
            fetch('/api/repos')
                .then(response => response.json())
                .then(data => {
                    renderRepos(data);
                    document.getElementById('last-update').textContent = 
                        `Last update: ${new Date().toLocaleTimeString()}`;
                })
                .catch(error => {
                    console.error('Error fetching data:', error);
                    showMessage('Error fetching repository data', 'error');
                });
        }
        
        function renderRepos(data) {
            const container = document.getElementById('repos-container');
            
            if (data.error) {
                container.innerHTML = `<div class="error">${data.error}</div>`;
                return;
            }
            
            if (!data.repos || data.repos.length === 0) {
                container.innerHTML = '<div class="error">No repositories found</div>';
                return;
            }
            
            const repoHtml = data.repos.map(repo => {
                if (!repo.is_repo) {
                    return `
                        <div class="repo">
                            <div class="repo-header">
                                <h3 class="repo-name">${repo.name}</h3>
                            </div>
                            <div class="error">${repo.error || 'Not a git repository'}</div>
                        </div>
                    `;
                }
                
                const badges = [];
                if (repo.has_uncommitted) badges.push(`<span class="badge dirty">${repo.uncommitted_count} uncommitted</span>`);
                if (repo.ahead > 0) badges.push(`<span class="badge ahead">${repo.ahead} ahead</span>`);
                if (repo.behind > 0) badges.push(`<span class="badge behind">${repo.behind} behind</span>`);
                if (repo.open_issues > 0) badges.push(`<span class="badge issues">${repo.open_issues} issues</span>`);
                if (!repo.has_uncommitted && repo.ahead === 0 && repo.behind === 0) badges.push(`<span class="badge clean">Clean</span>`);
                
                const commitInfo = repo.last_commit ? `
                    <div class="commit-info">
                        <div><span class="commit-hash">${repo.last_commit.hash}</span> ${repo.last_commit.message}</div>
                        <div style="color: #8b949e; margin-top: 5px;">by ${repo.last_commit.author} • ${repo.last_commit.time}</div>
                    </div>
                ` : '';
                
                const githubLink = repo.github_url ? `<a class="btn btn-sm" href="${repo.github_url}" target="_blank">GitHub</a>` : '';
                
                return `
                    <div class="repo" id="repo-${repo.name}">
                        <div class="repo-header">
                            <h3 class="repo-name">${repo.name}</h3>
                            <div class="repo-actions">
                                <button class="btn btn-sm primary" onclick="gitFetch('${repo.name}')" id="fetch-${repo.name}">📡 Fetch</button>
                                <button class="btn btn-sm" onclick="gitPull('${repo.name}')" id="pull-${repo.name}">⬇️ Pull</button>
                                ${githubLink}
                            </div>
                        </div>
                        
                        <div class="status-grid">
                            <span class="status-label">Branch:</span>
                            <span class="status-value">${repo.branch} ${badges.join('')}</span>
                            
                            <span class="status-label">Remote:</span>
                            <span class="status-value">${repo.upstream || 'None'}</span>
                        </div>
                        
                        ${commitInfo}
                        
                        ${repo.error ? `<div class="error">${repo.error}</div>` : ''}
                    </div>
                `;
            }).join('');
            
            container.innerHTML = `<div class="repos">${repoHtml}</div>`;
        }
        
        function gitFetch(repoName) {
            const btn = document.getElementById(`fetch-${repoName}`);
            btn.disabled = true;
            btn.textContent = '📡 Fetching...';
            
            fetch(`/api/repo/${repoName}/fetch`)
                .then(response => response.json())
                .then(data => {
                    btn.disabled = false;
                    btn.textContent = '📡 Fetch';
                    
                    if (data.success) {
                        showMessage(`Fetch completed for ${repoName}`, 'success');
                        // Update the specific repo display
                        if (data.repo_status) {
                            updateRepoDisplay(repoName, data.repo_status);
                        }
                    } else {
                        showMessage(`Fetch failed for ${repoName}: ${data.message}`, 'error');
                    }
                })
                .catch(error => {
                    btn.disabled = false;
                    btn.textContent = '📡 Fetch';
                    showMessage(`Fetch error for ${repoName}: ${error.message}`, 'error');
                });
        }
        
        function gitPull(repoName) {
            const btn = document.getElementById(`pull-${repoName}`);
            btn.disabled = true;
            btn.textContent = '⬇️ Pulling...';
            
            fetch(`/api/repo/${repoName}/pull`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({confirmed: false})
            })
            .then(response => response.json())
            .then(data => {
                btn.disabled = false;
                btn.textContent = '⬇️ Pull';
                
                if (data.need_confirmation) {
                    showConfirmationModal(repoName, data);
                } else if (data.success) {
                    showMessage(`Pull completed for ${repoName}`, 'success');
                    if (data.repo_status) {
                        updateRepoDisplay(repoName, data.repo_status);
                    }
                } else {
                    showMessage(`Pull failed for ${repoName}: ${data.message}`, 'error');
                }
            })
            .catch(error => {
                btn.disabled = false;
                btn.textContent = '⬇️ Pull';
                showMessage(`Pull error for ${repoName}: ${error.message}`, 'error');
            });
        }
        
        function showConfirmationModal(repoName, data) {
            const modal = document.getElementById('confirmation-modal');
            const details = document.getElementById('modal-details');
            const warning = document.getElementById('modal-warning');
            const confirmBtn = document.getElementById('confirm-pull-btn');
            
            details.innerHTML = `
                <p><strong>Repository:</strong> ${repoName}</p>
                <p><strong>Branch:</strong> ${data.details.branch}</p>
                <p><strong>Uncommitted changes:</strong> ${data.details.uncommitted_count}</p>
                <p><strong>Ahead/Behind:</strong> ${data.details.ahead}/${data.details.behind}</p>
            `;
            
            warning.textContent = data.warning;
            
            confirmBtn.onclick = () => {
                closeModal();
                confirmPull(repoName);
            };
            
            modal.classList.add('show');
        }
        
        function confirmPull(repoName) {
            const btn = document.getElementById(`pull-${repoName}`);
            btn.disabled = true;
            btn.textContent = '⬇️ Pulling...';
            
            fetch(`/api/repo/${repoName}/pull`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({confirmed: true})
            })
            .then(response => response.json())
            .then(data => {
                btn.disabled = false;
                btn.textContent = '⬇️ Pull';
                
                if (data.success) {
                    showMessage(`Pull completed for ${repoName} (forced)`, 'success');
                    if (data.repo_status) {
                        updateRepoDisplay(repoName, data.repo_status);
                    }
                } else {
                    showMessage(`Pull failed for ${repoName}: ${data.message}`, 'error');
                }
            })
            .catch(error => {
                btn.disabled = false;
                btn.textContent = '⬇️ Pull';
                showMessage(`Pull error for ${repoName}: ${error.message}`, 'error');
            });
        }
        
        function closeModal() {
            document.getElementById('confirmation-modal').classList.remove('show');
        }
        
        function updateRepoDisplay(repoName, repoStatus) {
            // This would update just the specific repo card
            // For simplicity, we'll just refresh all data
            setTimeout(refreshData, 500);
        }
        
        function showMessage(text, type) {
            // Remove any existing messages
            const existing = document.querySelector('.success-message, .error-message');
            if (existing) existing.remove();
            
            const message = document.createElement('div');
            message.className = type === 'success' ? 'success-message' : 'error-message';
            message.textContent = text;
            document.body.appendChild(message);
            
            setTimeout(() => message.remove(), 4000);
        }
        
        // Initialize
        refreshData();
        startAutoRefresh();
        
        // Close modal on escape key
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') closeModal();
        });
        
        // Close modal on backdrop click
        document.getElementById('confirmation-modal').addEventListener('click', (e) => {
            if (e.target.id === 'confirmation-modal') closeModal();
        });
    </script>
</body>
</html>'''
    
    def _send_response(self, status_code, content, content_type):
        """Send HTTP response"""
        self.send_response(status_code)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', len(content.encode('utf-8')))
        self.end_headers()
        self.wfile.write(content.encode('utf-8'))
    
    def _send_error_json(self, status_code, message):
        """Send error response as JSON"""
        error_response = json.dumps({'success': False, 'message': message})
        self._send_response(status_code, error_response, 'application/json')
    
    def _send_404(self):
        """Send 404 response"""
        self._send_response(404, '404 - Not Found', 'text/plain')
    
    def log_message(self, format, *args):
        """Override to customize logging"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        print(f'[{timestamp}] {format % args}')

def create_handler(git_dir):
    """Create handler with git directory"""
    def handler(*args, **kwargs):
        return DashboardHandler(git_dir, *args, **kwargs)
    return handler

def main():
    parser = argparse.ArgumentParser(description='Project Status Dashboard v2')
    parser.add_argument('--port', type=int, default=8766, help='Port to run on (default: 8766)')
    parser.add_argument('--git-dir', default=os.path.expanduser('~/git'), 
                       help='Directory containing git repositories')
    
    args = parser.parse_args()
    
    git_dir = Path(args.git_dir).expanduser().resolve()
    if not git_dir.exists():
        print(f"Error: Git directory {git_dir} does not exist")
        sys.exit(1)
    
    handler = create_handler(git_dir)
    server = HTTPServer(('', args.port), handler)
    
    print(f"""
🐱 Project Status Dashboard v2 starting...

📂 Git directory: {git_dir}
🌐 Server: http://localhost:{args.port}
📋 API: http://localhost:{args.port}/api/repos

Press Ctrl+C to stop
""")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n\n👋 Dashboard stopped")
        server.shutdown()

if __name__ == '__main__':
    main()