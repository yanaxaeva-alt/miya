#!/usr/bin/env bash
set -euo pipefail

MIYA_DIR="${MIYA_DIR:-$HOME/Documents/miya}"
HOME_DIR="${HOME}"
LAUNCH_AGENTS="${HOME}/Library/LaunchAgents"
LOG_DIR="${MIYA_DATA_DIR:-$HOME/.miaos}/logs"
BIN_DIR="${MIYA_DATA_DIR:-$HOME/.miaos}/bin"

mkdir -p "$LAUNCH_AGENTS" "$LOG_DIR" "$BIN_DIR"

render_plist() {
  local template="$1"
  local output="$2"
  sed \
    -e "s|__MIYA_DIR__|${MIYA_DIR}|g" \
    -e "s|__HOME__|${HOME_DIR}|g" \
    -e "s|__BIN_DIR__|${BIN_DIR}|g" \
    "$template" > "$output"
}

chmod +x "$MIYA_DIR/scripts/run-aeon-daemon.sh"
chmod +x "$MIYA_DIR/scripts/run-aeon-consolidate.sh"
cp "$MIYA_DIR/scripts/run-aeon-daemon.sh" "$BIN_DIR/run-aeon-daemon.sh"
cp "$MIYA_DIR/scripts/run-aeon-consolidate.sh" "$BIN_DIR/run-aeon-consolidate.sh"
chmod +x "$BIN_DIR/run-aeon-daemon.sh" "$BIN_DIR/run-aeon-consolidate.sh"

render_plist "$MIYA_DIR/scripts/com.miya.aeon-daemon.plist.template" "$LAUNCH_AGENTS/com.miya.aeon-daemon.plist"
render_plist "$MIYA_DIR/scripts/com.miya.aeon-consolidate.plist.template" "$LAUNCH_AGENTS/com.miya.aeon-consolidate.plist"

launchctl bootout "gui/$(id -u)/com.miya.aeon-daemon" 2>/dev/null || true
launchctl bootout "gui/$(id -u)/com.miya.aeon-consolidate" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$LAUNCH_AGENTS/com.miya.aeon-daemon.plist"
launchctl bootstrap "gui/$(id -u)" "$LAUNCH_AGENTS/com.miya.aeon-consolidate.plist"

echo "Installed AEON launchd agents:"
echo "  com.miya.aeon-daemon (continuous heartbeat, interval ${AEON_HEARTBEAT_INTERVAL:-15}s)"
echo "  com.miya.aeon-consolidate (daily 07:00)"
echo "Bin wrappers: $BIN_DIR"
echo "Logs: $LOG_DIR"
