# 035. The agent-facing CLI ships out of this repo

## Context

This repo carried its own Typer CLI (`src/agent_context/cli/`) with a `gac`
console script. It exposed `info`, journal commands, user management, and
(after ADR-034's original draft) the profile and protocol stores. The CLI
worked on the local filesystem through the `Facade`, not over HTTP.

That turned out to be the wrong home for it:

- **Two clients, two transports.** The `genesis` CLI in the my-agent-skills
  repo is an HTTP client against a genesis backend. The `gac` CLI was a
  local-filesystem tool against a different backend. Same shape of command,
  completely different mechanics, so habits did not transfer.
- **Duplicated surface.** Every new capability meant writing the command
  twice: once in the CLI, once in the API. The profile store was the clearest
  case. `gac profile` and `gac protocol` existed only because the in-repo CLI
  could not be reached over HTTP at all.
- **Local filesystem access.** The CLI read and wrote the markdown stores
  directly, with no auth and no per-user scoping from the API's point of
  view. The API already had the token-scoped, per-user path.

The agent-facing CLI belongs with the agent skills, not with the store it
talks to. The backend should expose the API; the client should live with the
agent that uses it.

## Decision

We will remove the in-repo CLI entirely and keep this repo a backend plus
Streamlit UI.

- Delete `src/agent_context/cli/` and its tests.
- Remove the `gac` console script from `pyproject.toml`. `gac-api` stays
  (`agent_context.api.cli`). `gac-ui` stays and moves to
  `agent_context.ui.cli`, since the UI is part of this product.
- Remove the `run-cli` Makefile target.
- The agent-facing CLI ships in the my-agent-skills repo and talks to this
  backend over the REST API.

The API surface is unchanged by this decision. `/protocol` and
`/profile/{target}` both stay, as do the journal routes. The only removal is
the in-process command layer.

## Status

Accepted

## Consequences

Positive:

- One client per backend. The agent CLI is an HTTP client like every other
  client, so the API is the only contract that has to hold.
- The API is the only surface, so it is the surface that gets tested and
  documented. The dead-route bug in `GET /journals/resolve` and
  `GET /journals/search` went unnoticed for exactly this reason: the CLI
  talked to the filesystem and never went through the router.
- No unauthenticated local-filesystem access path.

Negative:

- The Docker image can no longer create a user with `gac user create`. The
  bootstrap script calls the `agent_context.users` API directly instead.
- Anyone who used `uv run gac journals ...` locally must move to the
  my-agent-skills CLI (or the HTTP API directly).
- The in-repo `typer` dependency is gone. That was the only user of it.
