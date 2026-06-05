#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRONTEND_DIR="$ROOT_DIR/frontend"

BACKEND_HOST="${MIAOS_BACKEND_HOST:-127.0.0.1}"
BACKEND_PORT="${MIAOS_BACKEND_PORT:-8765}"
FRONTEND_HOST="${MIAOS_FRONTEND_HOST:-127.0.0.1}"
FRONTEND_PORT="${MIAOS_FRONTEND_PORT:-5173}"
API_BASE_URL="${VITE_API_BASE_URL:-http://${BACKEND_HOST}:${BACKEND_PORT}}"
FRONTEND_URL="http://${FRONTEND_HOST}:${FRONTEND_PORT}"

SETUP_ONLY=0

usage() {
  printf 'Usage: %s [--setup-only]\n' "$0"
  printf '\n'
  printf 'Environment overrides:\n'
  printf '  MIAOS_BACKEND_HOST    default: 127.0.0.1\n'
  printf '  MIAOS_BACKEND_PORT    default: 8765\n'
  printf '  MIAOS_FRONTEND_HOST   default: 127.0.0.1\n'
  printf '  MIAOS_FRONTEND_PORT   default: 5173\n'
  printf '  VITE_API_BASE_URL     default: http://127.0.0.1:8765\n'
}

case "${1:-}" in
  "")
    ;;
  "--setup-only")
    SETUP_ONLY=1
    ;;
  "-h" | "--help")
    usage
    exit 0
    ;;
  *)
    usage >&2
    exit 2
    ;;
esac

require_commands() {
  local missing=()
  local command_name

  for command_name in uv python3 node npm; do
    if ! command -v "$command_name" >/dev/null 2>&1; then
      missing+=("$command_name")
    fi
  done

  if ((${#missing[@]} > 0)); then
    printf 'Missing required command(s): %s\n' "${missing[*]}" >&2
    printf 'Install Python 3, uv, Node.js, and npm, then rerun this command.\n' >&2
    exit 1
  fi
}

setup_dependencies() {
  printf 'Installing backend dependencies with uv sync...\n'
  (cd "$ROOT_DIR" && uv sync)

  if [[ -d "$FRONTEND_DIR/node_modules" ]]; then
    printf 'Frontend dependencies already installed; skipping npm install.\n'
  else
    printf 'Installing frontend dependencies with npm install...\n'
    (cd "$FRONTEND_DIR" && npm install)
  fi
}

cleanup() {
  local exit_code=$?
  local pid

  trap - EXIT INT TERM

  printf '\nStopping MiaOS dev services...\n'
  for pid in "${BACKEND_PID:-}" "${FRONTEND_PID:-}"; do
    if [[ -n "$pid" ]] && kill -0 "$pid" >/dev/null 2>&1; then
      kill "$pid" >/dev/null 2>&1 || true
    fi
  done

  wait "${BACKEND_PID:-}" "${FRONTEND_PID:-}" >/dev/null 2>&1 || true
  exit "$exit_code"
}

require_commands
setup_dependencies

if ((SETUP_ONLY)); then
  printf 'Setup complete.\n'
  exit 0
fi

printf '\nStarting MiaOS Builder development stack...\n'
printf 'Backend URL:  %s\n' "$API_BASE_URL"
printf 'Frontend URL: %s\n' "$FRONTEND_URL"
printf 'Press Ctrl+C to stop both processes.\n\n'

trap cleanup EXIT INT TERM

(cd "$ROOT_DIR" && uv run uvicorn miaos.api:app --reload --host "$BACKEND_HOST" --port "$BACKEND_PORT") &
BACKEND_PID=$!

(
  cd "$FRONTEND_DIR"
  VITE_API_BASE_URL="$API_BASE_URL" npm run dev -- --host "$FRONTEND_HOST" --port "$FRONTEND_PORT"
) &
FRONTEND_PID=$!

wait -n "$BACKEND_PID" "$FRONTEND_PID"
