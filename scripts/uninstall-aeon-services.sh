#!/usr/bin/env bash
set -euo pipefail

launchctl bootout "gui/$(id -u)/com.miya.aeon-daemon" 2>/dev/null || true
launchctl bootout "gui/$(id -u)/com.miya.aeon-consolidate" 2>/dev/null || true
rm -f "$HOME/Library/LaunchAgents/com.miya.aeon-daemon.plist"
rm -f "$HOME/Library/LaunchAgents/com.miya.aeon-consolidate.plist"
echo "Removed AEON launchd agents."
