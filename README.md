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

# Profile store (persona + operating protocol)
uv run gac profile list
uv run gac profile read protocol
uv run gac profile write protocol --content "..."
uv run gac profile edit protocol --old "old" --new "new" --global-replace
uv run gac profile history protocol
uv run gac profile restore protocol --version 2026-10-22T031500000Z

# Operating protocol (same operations, target pinned)
uv run gac protocol read
uv run gac protocol write --content-file protocol.md
uv run gac protocol history
```

The profile store is exposed on the API under two paths: the generic
`/profile/{target}` routes (target `profile` or `protocol`) and the
entity-level `/protocol` routes, which are pinned to the operating
protocol. Both share one implementation.

## Architecture

```
src/agent_context/
  api/           FastAPI REST API (journals, profile, protocol endpoints)
  cli/           Typer CLI (info, journal commands, profile + protocol, user management)
  core/          Facade -- single entry point to all stores
  journal/       Journal facade (memory + memory-synthesis + daily-handover)
  profile/       Profile facade (profile.md, protocol.md, versions)
  backup/        Zip export/import (journals + profile)
  ui/            Streamlit UI (Memory, Persona, Protocol, Settings pages)
  users/         Per-user auth store (htpasswd)
```

## Docker

The image runs exactly what the host runs (`make serve`): the Streamlit
UI on :3001 and the FastAPI API on :8766.

```bash
# Build
docker build -t genesis-agent-context:local .

# Run (four XDG roots are bind-mounted; PUID/PGID keep files host-owned)
mkdir -p /tmp/gac-smoke/{config,data,state,cache}
docker run -d --name gac-smoke \
  -p 3001:3001 -p 8766:8766 \
  -e PUID=$(id -u) -e PGID=$(id -g) \
  -v /tmp/gac-smoke/config:/home/gac/.config \
  -v /tmp/gac-smoke/data:/home/gac/.local/share \
  -v /tmp/gac-smoke/state:/home/gac/.local/state \
  -v /tmp/gac-smoke/cache:/home/gac/.cache \
  genesis-agent-context:local

# Health
curl -fsS http://127.0.0.1:8766/health
```

`make docker-build` and `make docker-run` wrap the same commands with
local state under `.docker-data/`.

### First account

Two paths, both supported:

1. **UI sign-up (default).** No bootstrap variables are set, so the
   container creates no account. Open the UI on :3001 and create the
   first user through the sign-up form.
2. **Opt-in bootstrap.** Set `GAC_BOOTSTRAP_USER` and
   `GAC_BOOTSTRAP_PASSWORD` to have the entrypoint create that account
   on first start (idempotent: if the users table already exists,
   nothing is touched).

```bash
docker run -d --name gac-smoke \
  -p 3001:3001 -p 8766:8766 \
  -e PUID=$(id -u) -e PGID=$(id -g) \
  -e GAC_BOOTSTRAP_USER=admin -e GAC_BOOTSTRAP_PASSWORD=admin123 \
  -v /tmp/gac-smoke/config:/home/gac/.config \
  -v /tmp/gac-smoke/data:/home/gac/.local/share \
  -v /tmp/gac-smoke/state:/home/gac/.local/state \
  -v /tmp/gac-smoke/cache:/home/gac/.cache \
  genesis-agent-context:local
```

The bootstrap password lands in the container environment (visible in
`docker inspect`), so rotate it after first boot.

### Notes

- The API secret and the session cookie key are generated on first use
  under the data mount (`/home/gac/.local/share/agent-context/`). They
  survive restarts; rotating them logs everyone out.
- Images are built by CI on pushes to `main` and pushed to
  `ghcr.io/genesis-scaffolding/genesis-agent-context` (private):
  `latest`, `sha-<short>`, and version tags.
