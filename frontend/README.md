# Miya Editor

React/Vite editor for the local MiaOS + AEON backend.

## Run

From the repository root:

```bash
cd ~/Documents/miya/frontend
pnpm install
./scripts/start-miaos-backend.sh
pnpm dev
```

The editor runs on `http://localhost:5173` and proxies `/api/miaos/*` to the backend on `http://127.0.0.1:8000`.

Quick backend smoke:

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/api/status
```

If the toolbar says `Backend MiaOS offline`, start the backend from this monorepo path:

```bash
cd ~/Documents/miya/frontend
./scripts/start-miaos-backend.sh
```

Do not start a second `pnpm dev` if `http://localhost:5173` is already open.

## Local MLX Model

The backend can use a local MLX model as the default provider:

```bash
cd ~/Documents/miya/frontend
MIYA_PROVIDER=mlx MIYA_MLX_MODEL="/absolute/path/to/mlx-model" ./scripts/start-miaos-backend.sh
```

`MIYA_MLX_MODEL` can be an absolute local model directory or a HuggingFace/MLX repo id, for example:

```bash
MIYA_PROVIDER=mlx MIYA_MLX_MODEL="mlx-community/Qwen2.5-7B-Instruct-4bit" ./scripts/start-miaos-backend.sh
```

## oMLX Server Provider

If oMLX already has a stronger model loaded, run oMLX on a separate port and let MiaOS call it as an OpenAI-compatible provider:

```bash
~/.omlx/bin/omlx serve --model-dir ~/.omlx/models --port 8010
```

Then start MiaOS with the `omlx` provider:

```bash
cd ~/Documents/miya/frontend
MIYA_PROVIDER=omlx MIYA_OMLX_BASE_URL="http://127.0.0.1:8010" MIYA_OMLX_MODEL="your-model-id" ./scripts/start-miaos-backend.sh
```

Ports:

- `8010` — oMLX model server
- `8000` — MiaOS backend
- `5173` — Miya Editor

## Checks

```bash
cd ~/Documents/miya/frontend
pnpm exec tsc --noEmit
pnpm run lint
pnpm run build
```

Repository-level Python checks:

```bash
cd ~/Documents/miya
uv run pytest
```
