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
