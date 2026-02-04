# Project Status Dashboard

A simple web dashboard showing git status across local repositories.

![Python](https://img.shields.io/badge/python-3.11+-blue)
![No Dependencies](https://img.shields.io/badge/dependencies-none-green)

## Features

- **Repository Overview**: Shows all git repos in `~/git/`
- **Status at a Glance**:
  - Current branch
  - Uncommitted changes (count)
  - Ahead/behind remote tracking
  - Last commit (message, author, relative time)
- **GitHub Integration**: Open issues count via `gh` CLI
- **Auto-refresh**: Updates every 60 seconds
- **Dark Theme**: Easy on the eyes, matches the friday-ui aesthetic
- **JSON API**: `/api/repos` endpoint for programmatic access

## Installation

```bash
# Clone the repo
git clone git@github.com:wortmanb/project-status-dashboard.git ~/git/project-status-dashboard

# Make it executable
chmod +x ~/git/project-status-dashboard/dashboard.py

# Optional: symlink to ~/bin
ln -s ~/git/project-status-dashboard/dashboard.py ~/bin/project-dashboard
```

## Usage

```bash
# Run the dashboard
./dashboard.py

# Or via symlink
project-dashboard
```

Then open http://localhost:8765 in your browser.

## Configuration

Edit the constants at the top of `dashboard.py`:

```python
GIT_DIR = Path.home() / "git"  # Directory to scan for repos
PORT = 8765                     # Web server port
```

## API

### GET /
Returns the HTML dashboard.

### GET /api/repos
Returns JSON array of repository status:

```json
[
  {
    "name": "project-name",
    "path": "/home/user/git/project-name",
    "branch": "main",
    "has_changes": true,
    "change_count": 3,
    "ahead": 1,
    "behind": 0,
    "last_commit": {
      "hash": "abc1234",
      "message": "feat: add new feature",
      "author": "username",
      "time": "2 hours ago"
    },
    "github_url": "https://github.com/owner/repo",
    "github_issues": 5
  }
]
```

## Requirements

- Python 3.11+
- `gh` CLI (optional, for GitHub issues count)
- No external Python dependencies

## Running as a Service

Create a systemd user service at `~/.config/systemd/user/project-dashboard.service`:

```ini
[Unit]
Description=Project Status Dashboard
After=network.target

[Service]
ExecStart=/home/bret/git/project-status-dashboard/dashboard.py
Restart=on-failure

[Install]
WantedBy=default.target
```

Enable and start:

```bash
systemctl --user enable project-dashboard
systemctl --user start project-dashboard
```

## License

MIT
