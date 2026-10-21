# genesis-agent-context

Agent persona, memory, and handover stores for AI agents. REST API + Streamlit UI.

## Purpose

Provides three stores backed by markdown-on-disk:

- **Persona** — agent persona markdown file with version snapshots (target: ``profile``)
- **Protocol** — agent operating protocol markdown file with version snapshots (target: ``protocol``)
- **Memory** — per-day journal entries with three types: ``memory``, ``memory-synthesis``, ``daily-handover``

Architecture mirrors [genesis-productivity](https://github.com/gentran/genesis-productivity) (tasks, calendar, contacts, XP stripped).

## Running

```bash
# Install
uv sync

# API server (port 8766)
uv run gac-api

# UI (port 3001)
uv run gac-ui
```

## CLI

```bash
# Show config
uv run gac info

# Journal entries
uv run gac journals list
uv run gac journals read <uid>
uv run gac journals create "content here" --type memory
uv run gac journals delete <uid>
```

## Architecture

```
src/agent_context/
  api/           FastAPI REST API (journals, profile endpoints)
  cli/           Typer CLI (info, journal commands, user management)
  core/          Facade -- single entry point to all stores
  journal/       Journal facade (memory + memory-synthesis + daily-handover)
  profile/       Profile facade (profile.md, protocol.md, versions)
  backup/        Zip export/import (journals + profile)
  ui/            Streamlit UI (Memory, Persona, Protocol, Settings pages)
  users/         Per-user auth store (htpasswd)
```
