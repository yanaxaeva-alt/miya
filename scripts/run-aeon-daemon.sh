#!/usr/bin/env bash
set -euo pipefail

MIYA_DIR="${MIYA_DIR:-$HOME/Documents/miya}"
MIYA_DATA_DIR="${MIYA_DATA_DIR:-$HOME/.miaos}"
UV_BIN="${UV_BIN:-$HOME/.local/bin/uv}"

cd "$MIYA_DIR"
export MIYA_DATA_DIR
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"
exec "$UV_BIN" run aeon daemon --interval "${AEON_HEARTBEAT_INTERVAL:-15}"
