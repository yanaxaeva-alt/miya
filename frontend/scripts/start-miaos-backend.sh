#!/usr/bin/env bash
set -euo pipefail

MIYA_DIR="${MIYA_DIR:-$HOME/Documents/miya}"

if ! command -v uv >/dev/null 2>&1; then
  echo "uv не найден. Установите Astral uv (нужен Python 3.12+ для MiaOS):"
  echo "  curl -LsSf https://astral.sh/uv/install.sh | sh"
  echo "Затем перезапустите терминал и снова выполните этот скрипт."
  exit 1
fi

if [[ ! -d "$MIYA_DIR" ]]; then
  echo "Не найден каталог MiaOS: $MIYA_DIR"
  exit 1
fi

cd "$MIYA_DIR"
echo "→ uv sync (Documents/miya)"
uv sync
if [[ "${MIYA_WITH_MLX:-1}" == "1" ]]; then
  echo "→ uv sync --group mlx (Apple Silicon inference)"
  uv sync --group mlx
fi

PORT="${MIYA_PORT:-8000}"
if PIDS=$(lsof -tiTCP:"$PORT" -sTCP:LISTEN 2>/dev/null); then
  echo "→ порт $PORT занят — останавливаем старый backend (PIDs: $PIDS)"
  kill $PIDS 2>/dev/null || true
  sleep 1
fi

echo "→ backend http://127.0.0.1:$PORT  (health: /health, /api/status)"
exec uv run uvicorn miaos.api:app --reload --port "$PORT"
