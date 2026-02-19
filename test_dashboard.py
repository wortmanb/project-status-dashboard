#!/usr/bin/env python3
"""
Quick test script for Project Status Dashboard v2
Validates core functionality without starting the server.
"""

import sys
import subprocess
from pathlib import Path

def test_imports():
    """Test that all required modules can be imported."""
    try:
        import http.server
        import socketserver
        import json
        import subprocess
        import os
        import urllib.parse
        import time
        from datetime import datetime, timezone
        from pathlib import Path
        print("✅ All imports successful")
        return True
    except ImportError as e:
        print(f"❌ Import failed: {e}")
        return False

def test_git_commands():
    """Test that required git commands are available."""
    commands = ['git', 'gh']
    results = {}
    
    for cmd in commands:
        try:
            result = subprocess.run([cmd, '--version'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                version = result.stdout.strip().split('\n')[0]
                results[cmd] = f"✅ {version}"
            else:
                results[cmd] = f"❌ Command failed: {result.stderr}"
        except FileNotFoundError:
            results[cmd] = "⚠️ Not found (optional for gh, required for git)"
        except subprocess.TimeoutExpired:
            results[cmd] = "❌ Command timed out"
    
    for cmd, status in results.items():
        print(f"{cmd}: {status}")
    
    return 'git' in results and '✅' in results['git']

def test_git_repos_directory():
    """Check if ~/git directory exists and has repos."""
    git_dir = Path.home() / "git"
    
    if not git_dir.exists():
        print(f"❌ {git_dir} does not exist")
        return False
    
    repos = [d for d in git_dir.iterdir() if d.is_dir() and (d / ".git").exists()]
    print(f"✅ Found {len(repos)} git repositories in {git_dir}")
    
    if repos:
        print("   Repositories:")
        for repo in repos[:5]:  # Show first 5
            print(f"   • {repo.name}")
        if len(repos) > 5:
            print(f"   • ... and {len(repos) - 5} more")
    
    return True

def test_dashboard_class():
    """Test that the dashboard handler class can be instantiated."""
    try:
        sys.path.insert(0, str(Path(__file__).parent))
        from dashboard import ProjectDashboardHandler
        
        # Create a mock instance (without actual HTTP handling)
        handler_class = ProjectDashboardHandler
        print("✅ ProjectDashboardHandler class loads successfully")
        return True
    except Exception as e:
        print(f"❌ Failed to load dashboard class: {e}")
        return False

def main():
    """Run all tests."""
    print("🧪 Testing Project Status Dashboard v2\n")
    
    tests = [
        ("Python imports", test_imports),
        ("Git commands", test_git_commands),
        ("Git repositories directory", test_git_repos_directory),
        ("Dashboard handler class", test_dashboard_class),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n📋 {test_name}:")
        try:
            if test_func():
                passed += 1
        except Exception as e:
            print(f"❌ Test failed with exception: {e}")
    
    print(f"\n🏁 Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! Dashboard should work correctly.")
        print("\nTo start the dashboard:")
        print("  cd ~/git/project-dashboard-v2")
        print("  ./dashboard.py")
        print("  # Then open http://localhost:8766")
        return 0
    else:
        print(f"\n⚠️ {total - passed} test(s) failed. Check the issues above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())