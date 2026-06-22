# AEON without GCS

AEON-light runtime built on top of MiaOS. It implements the eight AEON layers except **Generative Cognitive Substrate (GCS)**.

## What is included

| Layer | Component | Implementation |
| --- | --- | --- |
| 1 | Embodied Interface | Local snapshot sensors (`cwd`, recent files, hostname, optional project dir) |
| 2 | Substrate Memory | MiaOS `MemoryStore` episodes + skill notes |
| 3 | Active Inference Loop | Heuristic surprise heartbeat with side effects |
| 4 | Open-ended Goal Pool | Seed + user + curiosity goals; persisted to `{base_dir}/aeon_goals.json` |
| 5 | Execution | **Fixed** MiaOS chat or graph templates (`chat-memory-loop`, `mia-minimal`) |
| 6 | Identity Core | Mia `.mia` persona package |
| 7 | Meta-governance | Safety, drift, anomaly monitors |
| 8 | Constitutional Core | Tier 0–3 rule gate + Tier 2 approval queue |

## Quick start

```bash
cd ~/Documents/miya
uv sync --group dev
export MIYA_DATA_DIR=~/.miaos   # optional; default is .miaos in cwd
uv run aeon status
uv run aeon ask "Привет, Мия!"
uv run aeon tick
uv run aeon goals add "Ship feature" "Finish AEON persistence"
uv run aeon consolidate
uv run aeon daemon
```

## Configuration

Default config: `config/aeon.default.yaml`

Override with:

```bash
uv run aeon ask "..." --config /path/to/aeon.yaml
```

Data directory defaults to `.miaos/` (same as MiaOS API state). Override with `MIYA_DATA_DIR`.

Optional embodied project watch:

```bash
export MIYA_PROJECT_DIR=~/Documents/miya/frontend
```

## Persistence and consolidation

- User goals and progress are saved to `aeon_goals.json` under the MiaOS base dir.
- Heartbeat ticks append to `aeon_ticks.jsonl`.
- `consolidate()` retires stale goals, bumps progress from episodes, and writes structured skill notes.
- The API caches one `AeonRuntime` per `package_id:provider` so heartbeat and goals survive between requests.
- Tier 2 constitutional checkpoints enqueue items in MiaOS Approval Queue.

## Always-on macOS services

```bash
~/Documents/miya/scripts/install-aeon-services.sh
# com.miya.aeon-daemon — continuous heartbeat
# com.miya.aeon-consolidate — daily 07:00 consolidation

~/Documents/miya/scripts/uninstall-aeon-services.sh
```

## Architecture choice

Layer 5 deliberately avoids ephemeral agent synthesis. Instead:

- short requests → `ChatSession`
- complex requests → fixed MiaOS graph templates

This gives most of the AEON safety/memory/heartbeat structure without GCS complexity.

## Editor integration

Miya Editor includes **AEON Studio** (`#miya-aeon-studio`) wired to:

- `GET /aeon/status`
- `POST /aeon/ask`
- `POST /aeon/tick`
- `POST /aeon/goals`
- `POST /aeon/goals/{id}/deactivate`
- `POST /aeon/consolidate`

The editor has an **AEON** tab with AEON Studio and the v1.0 acceptance checklist.

Start backend + editor:

```bash
~/Documents/miya/frontend/scripts/start-miaos-backend.sh
cd ~/Documents/miya/frontend && pnpm dev
```

Open the **AEON** tab to use AEON Studio.
