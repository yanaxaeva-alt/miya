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

Full local doctor:

```bash
cd ~/Documents/miya
uv run python scripts/miaos-doctor.py
```

The doctor checks backend health, provider selection, persona model binding, and AEON status.

## v1.0 Smoke Scenario

After the editor opens:

1. Open **Модели и персона** and confirm the main model/provider is visible.
2. Open **AEON**, ask a short question, add a goal, and click **Закрепить память**.
3. Open **Память** and confirm the latest chat episode appears without internal context or trace IDs.
4. Open **Граф**, load `mia-minimal` from templates if the canvas is empty, select **Тестовый режим**, and run the graph. The expected state is **ожидает подтверждения**.
5. Open **Качество**, select **Тестовый режим**, and run `golden_mvp`. The expected result is `ПРОЙДЕНО · 3/3`.

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
MIYA_WITH_MLX=1 MIYA_PROVIDER=mlx MIYA_MLX_MODEL="/absolute/path/to/mlx-model" ./scripts/start-miaos-backend.sh
```

`MIYA_MLX_MODEL` can be an absolute local model directory or a HuggingFace/MLX repo id, for example:

```bash
MIYA_WITH_MLX=1 MIYA_PROVIDER=mlx MIYA_MLX_MODEL="mlx-community/Qwen2.5-7B-Instruct-4bit" ./scripts/start-miaos-backend.sh
```

Plain `./scripts/start-miaos-backend.sh` skips direct MLX dependencies so the API starts quickly. Use `MIYA_WITH_MLX=1` only when you specifically want the built-in `mlx-lm` provider.

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

You can also select the oMLX model in **Models & Persona → Model Studio**. The selection is saved to `.miaos/settings.json` and reused when the backend restarts.

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
