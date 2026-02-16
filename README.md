# Project Status Dashboard v2

Enhanced web dashboard for monitoring git repositories with **interactive git operations**. This is a significant upgrade from v1 with clickable sync/fetch buttons, confirmation dialogs, and real-time status updates.

## 🚀 New in v2

### Interactive Git Operations
- **📡 Fetch Button**: Updates remote refs without changing working directory
- **⬇️ Pull Button**: Pulls latest changes with safety checks
- **Smart validation**: Won't pull if working directory has uncommitted changes
- **Confirmation dialogs**: Prevents accidental operations with detailed info
- **Real-time feedback**: Shows operation progress and results

### Enhanced UX
- **AJAX operations**: No full page reloads needed
- **Operation status**: Success/error messages with command output
- **Auto-refresh toggle**: Can disable 60-second auto-refresh
- **Responsive design**: Works on mobile devices
- **Loading states**: Button text changes during operations

### Safety Features
- **Pre-pull validation**: Checks for uncommitted changes
- **Confirmation modals**: Shows repo details before destructive operations
- **Operation timeouts**: Git operations won't hang indefinitely
- **Error handling**: Clear error messages with stderr output

## 🔧 Features

### Repository Monitoring
- **Real-time scanning** of `~/git/` directory
- **Git status tracking**: uncommitted changes, ahead/behind counts
- **Branch information** with current branch display
- **Last commit details**: hash, message, author, time
- **GitHub integration**: clickable links and open issue counts
- **Clean/dirty indicators**: color-coded cards based on repo status

### Interactive Operations
```bash
# Available operations per repository:
📡 Fetch   # Updates remote tracking branches (safe, read-only)
⬇️ Pull    # Merges remote changes (requires clean working directory)
```

### Dashboard Stats
- **Total repositories** count
- **Repositories needing attention** (uncommitted, ahead, behind)
- **Last updated timestamp**
- **Auto-refresh status** (can be toggled)

## 📖 Usage

### Start the Dashboard
```bash
cd ~/git/project-dashboard-v2
./dashboard.py

# Or install globally:
ln -s ~/git/project-dashboard-v2/dashboard.py ~/bin/project-dashboard-v2
project-dashboard-v2
```

**Default URL:** http://localhost:8766 (port 8766 to avoid conflicts with v1)

### Git Operations Workflow

1. **View Repository Status**: Cards show current state (clean/needs attention)

2. **Fetch Updates**: Click "📡 Fetch" to update remote refs
   - Safe operation (read-only)
   - Updates ahead/behind counts
   - No confirmation needed

3. **Pull Changes**: Click "⬇️ Pull" to merge remote changes
   - Shows confirmation dialog with repo details
   - Validates working directory is clean
   - Displays operation results with output

4. **Monitor Results**: Success/error messages appear below repo cards

### API Endpoints

- `GET /` - Main dashboard interface
- `GET /api/repos` - JSON repository data
- `GET /api/repo/{name}/fetch` - Fetch repository updates
- `POST /api/repo/{name}/pull` - Pull repository changes

## 🎯 Use Cases

### Daily Development Workflow
```bash
# Morning routine:
1. Open dashboard (http://localhost:8766)
2. Click "Fetch" on all repos to see what's new
3. Review ahead/behind counts
4. Pull updates for specific repos as needed
```

### Team Collaboration
- **Before starting work**: Fetch all repos to see latest remote state
- **After remote changes**: Pull button shows exactly what will be merged
- **Safety checks**: Won't accidentally lose uncommitted work

### Repository Maintenance
- **Quick health check**: See all repos needing attention at a glance
- **Batch operations**: Fetch multiple repos quickly
- **Status tracking**: Monitor which repos are falling behind

## 🔒 Safety Guarantees

### Pre-operation Validation
- **Fetch operations**: Always safe (read-only remote updates)
- **Pull operations**: Blocked if working directory has uncommitted changes
- **Timeout protection**: Operations won't hang indefinitely (30s fetch, 60s pull)

### Confirmation Dialogs
Before any pull operation, you'll see:
- Repository name and current branch
- Number of commits behind
- Uncommitted changes count
- Warning if pull will fail due to uncommitted changes

### Error Handling
- **Clear error messages** with specific failure reasons
- **Command output display** (stdout/stderr) for debugging
- **Operation recovery**: Failed operations don't break the interface

## 📊 Comparison with v1

| Feature | v1 | v2 |
|---------|----|----|
| Repository monitoring | ✅ | ✅ |
| GitHub integration | ✅ | ✅ |
| Auto-refresh | ✅ | ✅ (toggleable) |
| Interactive git ops | ❌ | ✅ |
| Fetch button | ❌ | ✅ |
| Pull button | ❌ | ✅ |
| Confirmation dialogs | ❌ | ✅ |
| Real-time updates | ❌ | ✅ |
| Operation feedback | ❌ | ✅ |
| Safety validation | ❌ | ✅ |

## 🛠 Technical Details

### Architecture
- **Single-file Python application** using stdlib `http.server`
- **Zero external dependencies** (pure Python 3.11+)
- **Responsive web interface** with JavaScript AJAX calls
- **RESTful API** for programmatic access

### Git Integration
- **Safe subprocess calls** with timeout protection
- **Working directory isolation** (changes back to original directory)
- **Error code validation** with meaningful error messages
- **Output capture** for user feedback

### Performance
- **Parallel repository scanning** for fast initial load
- **Incremental updates** via AJAX (no full page reloads)
- **Efficient DOM updates** (only changes affected elements)
- **Background auto-refresh** with minimal resource usage

## 🚀 Installation

### Standalone
```bash
cd ~/git/project-dashboard-v2
./dashboard.py
```

### Global Installation
```bash
# Create symlink for global access
ln -s ~/git/project-dashboard-v2/dashboard.py ~/bin/project-dashboard-v2

# Run from anywhere
project-dashboard-v2
```

### Requirements
- **Python 3.11+** (uses stdlib only)
- **Git CLI** (for repository operations)
- **gh CLI** (optional, for GitHub issue counts)

## 🎨 UI/UX

### Visual Indicators
- **🟢 Green border**: Repository is clean and up-to-date
- **🔴 Red border**: Repository needs attention (uncommitted/behind/ahead)
- **Color-coded status badges**: Uncommitted (yellow), ahead (green), behind (red)
- **Loading states**: Buttons show progress during operations
- **Success/error messages**: Clear feedback with command output

### Responsive Design
- **Desktop**: Grid layout with multiple columns
- **Mobile**: Single-column layout with touch-friendly buttons
- **Dark theme**: GitHub-inspired color scheme
- **Accessible**: High contrast, clear typography

---

**Version:** 2.0  
**Compatible with:** Python 3.11+, All major browsers  
**License:** MIT  
**Author:** Built by Friday (nightly build 2026-02-16)