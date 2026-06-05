# MiaOS Builder

Runtime-first local builder for MiaOS virtual personalities. The current developer
workflow runs a FastAPI backend and Vite frontend locally; desktop packaging is
intentionally out of scope for this stage.

## Quick Start

### Prerequisites

- Python 3.12+
- [`uv`](https://docs.astral.sh/uv/)
- Node.js and npm

### Setup

```bash
make setup
```

This runs `uv sync` for the backend and installs frontend dependencies with
`npm install` when `frontend/node_modules` is missing.

### Run the UI and backend

```bash
make dev
```

`make dev` also performs setup checks, then starts both local services:

- Backend API: `http://127.0.0.1:8765`
- Frontend UI: `http://127.0.0.1:5173`

Open `http://127.0.0.1:5173` in a browser to use MiaOS Builder.

The frontend receives the backend URL through:

```bash
VITE_API_BASE_URL=http://127.0.0.1:8765
```

### Run checks

```bash
make check
```

This runs linting, type checks, the frontend build, and backend tests.

## Development commands

```bash
make setup      # install backend and frontend dependencies
make dev        # start FastAPI and Vite together
make test       # run backend tests
make lint       # run backend and frontend linters
make typecheck  # run backend mypy and frontend TypeScript build
make check      # run lint, typecheck, and test
make clean      # remove local build and test artifacts
```

The backend development server command is:

```bash
uv run uvicorn miaos.api:app --reload --host 127.0.0.1 --port 8765
```

## Not included yet

This repository does not yet include Tauri packaging, a `.dmg` installer,
notarization, auto-update, launch daemons, or writes to system directories.
