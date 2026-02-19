# Project Status Dashboard v2 🐱

Enhanced interactive dashboard for monitoring and managing git repositories with clickable operations.

**Evolution from v1:** This is the next generation of the project status dashboard, adding interactive git operations with safety guardrails and confirmation dialogs.

## Features

### 🔍 Visual Monitoring
- **Real-time status** for all repositories in `~/git/`
- **Branch information** with ahead/behind counts
- **Uncommitted changes** detection and display
- **Last commit details** (hash, message, author, relative time)
- **GitHub integration** with issue counts (requires `gh` CLI)
- **Auto-refresh** every 60 seconds with pause/resume controls

### 🎛️ Interactive Operations
- **📡 Fetch Button**: Safe git fetch operation for each repository
- **⬇️ Pull Button**: Git pull with intelligent safety checks
- **Real-time feedback** with loading states and operation results
- **AJAX updates** without page reloads

### 🛡️ Safety Features
- **Uncommitted change detection**: Won't allow pulls that could fail
- **Confirmation dialogs**: Shows exactly what will happen before destructive operations
- **Operation feedback**: Real-time status with stdout/stderr output
- **Timeout protection**: Commands won't hang indefinitely
- **Non-destructive defaults**: Fetch is always safe and encouraged

### 📱 User Experience
- **Modern dark theme** inspired by GitHub
- **Mobile responsive** design that works on any device
- **Toast notifications** for operation feedback
- **Modal confirmations** with detailed repository information
- **Keyboard shortcuts** (ESC to close modals)
- **RESTful API** for programmatic access

## Installation & Usage

### Quick Start
```bash
cd ~/git/project-dashboard-v2
./dashboard.py
```

### Options
```bash
./dashboard.py --port 8766 --git-dir ~/git
```

### System Installation
```bash
# Create symlink for system-wide access
ln -sf ~/git/project-dashboard-v2/dashboard.py ~/bin/project-dashboard-v2
chmod +x ~/git/project-dashboard-v2/dashboard.py
```

### Access
- **Web Interface**: http://localhost:8766
- **JSON API**: http://localhost:8766/api/repos
- **Individual Repo API**: http://localhost:8766/api/repo/{name}/fetch

## API Endpoints

### GET /api/repos
Returns comprehensive status for all repositories:
```json
{
  "scan_time": "2026-02-19T07:00:00Z",
  "git_dir": "/home/user/git",
  "total_repos": 12,
  "repos": [
    {
      "name": "my-project",
      "branch": "main",
      "has_uncommitted": true,
      "uncommitted_count": 3,
      "ahead": 2,
      "behind": 1,
      "last_commit": {
        "hash": "c5ba60a",
        "message": "Add new feature",
        "author": "Developer",
        "time": "2 hours ago"
      },
      "github_url": "https://github.com/user/my-project",
      "open_issues": 5
    }
  ]
}
```

### GET /api/repo/{name}/fetch
Performs safe git fetch operation:
```json
{
  "success": true,
  "message": "Fetch completed successfully",
  "output": "From github.com:user/repo\n   c5ba60a..f8d9e2b  main -> origin/main",
  "repo_status": { /* updated repo status */ }
}
```

### POST /api/repo/{name}/pull
Performs git pull with safety checks:
```json
// Request body
{
  "confirmed": false  // Set to true to bypass safety checks
}

// Response (if confirmation needed)
{
  "success": false,
  "need_confirmation": true,
  "message": "Repository has 3 uncommitted changes",
  "details": {
    "branch": "main",
    "uncommitted_count": 3,
    "ahead": 2,
    "behind": 1
  },
  "warning": "Pull may fail or create merge conflicts. Confirm to continue."
}
```

## Safety Workflow

### Fetch Operations (Always Safe)
1. Click **📡 Fetch** button
2. Repository fetches latest remote information
3. UI updates with new ahead/behind counts
4. No risk of conflicts or data loss

### Pull Operations (With Safety Checks)
1. Click **⬇️ Pull** button
2. System checks for uncommitted changes
3. If changes detected:
   - Shows confirmation modal with repository details
   - User can cancel or proceed with warning
4. If safe or confirmed:
   - Performs git pull
   - Updates UI with results
   - Shows success/error message

## Technical Architecture

### Backend
- **Pure Python stdlib** HTTP server (no external dependencies)
- **Threaded request handling** for concurrent operations
- **Subprocess timeout protection** prevents hanging
- **Working directory isolation** for git operations
- **Comprehensive error handling** with user-friendly messages

### Frontend
- **Vanilla JavaScript** with modern async/await patterns
- **CSS Grid layout** for responsive design
- **Real-time AJAX** updates without page reloads
- **Progressive enhancement** - works with JavaScript disabled
- **Accessibility features** - keyboard navigation, screen reader friendly

### Security Considerations
- **No destructive operations** without explicit confirmation
- **Timeout protection** prevents resource exhaustion
- **Input validation** on repository names
- **Safe subprocess execution** with proper escaping

## Comparison with v1

| Feature | v1 | v2 |
|---------|----|----|
| Repository Status | ✅ Read-only display | ✅ Read-only display |
| Git Operations | ❌ Manual CLI required | ✅ Click to fetch/pull |
| Safety Checks | ❌ None | ✅ Uncommitted change detection |
| User Feedback | ❌ None | ✅ Real-time notifications |
| Confirmations | ❌ None | ✅ Modal dialogs with details |
| Mobile Support | ✅ Basic responsive | ✅ Enhanced mobile UX |
| API Access | ✅ JSON endpoint | ✅ Enhanced RESTful API |
| Port | 8765 | 8766 |

## Use Cases

### Daily Development Workflow
1. **Morning routine**: Open dashboard to see overnight changes
2. **Batch fetch**: Click fetch on all repositories to get latest remote info
3. **Selective pull**: Only pull repositories that need updates
4. **Status overview**: Quick visual check of all projects at once

### Team Collaboration
- **Pre-standup**: Ensure all repositories are up-to-date
- **Before deployment**: Verify clean state across all projects
- **Code review prep**: Fetch latest changes before creating pull requests

### Repository Maintenance
- **Bulk operations**: Fetch all repositories efficiently
- **Change detection**: Visual indication of uncommitted work
- **Branch awareness**: Track feature branch status across projects

## Tech Stack

- **Backend**: Python 3.8+ (stdlib only)
- **Frontend**: Vanilla HTML5/CSS3/JavaScript (ES6+)
- **Architecture**: Single-file HTTP server with embedded frontend
- **Dependencies**: None (pure stdlib implementation)
- **Performance**: Parallel git operations, efficient status caching
- **Compatibility**: Works on any system with Python and git

## Version History

- **v2.0**: Interactive git operations with safety checks
- **v1.0**: Read-only repository status dashboard

---

**Port Conflict Note**: v2 runs on port 8766 to avoid conflicts with v1 (port 8765). Both can run simultaneously for comparison.

*Part of the Friday nightly builds series - building useful tools one commit at a time.* 🌙