# genesis-agent-context

Agent persona, memory, and handover stores for AI agents. REST API + Streamlit UI.

## Purpose

Provides three stores backed by markdown-on-disk:

- **Persona** — profile and life-story markdown files with version snapshots
- **Memory** — per-day journal entries with type `memory`
- **Handover** — per-day journal entries with type `handover`

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
uv run gac journals create "content here" --type daily
uv run gac journals delete <uid>
```

## Architecture

```
src/agent_context/
  api/           FastAPI REST API (journals, profile endpoints)
  cli/           Typer CLI (info, journal commands, user management)
  core/          Facade — single entry point to all stores
  journal/       Journal facade (memory + handover + other entry types)
  profile/       Profile facade (profile.md, life_story.md, versions)
  backup/       Zip export/import (journals + profile)
  ui/           Streamlit UI (journal, profile, settings pages)
  users/        Per-user auth store (htpasswd)
```
