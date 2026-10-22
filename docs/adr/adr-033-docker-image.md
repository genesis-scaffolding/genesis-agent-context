# 033. Docker image for the agent-context system

## Context

Forces at play. The system currently runs by cloning the repo and
`make serve` (uv + streamlit on :3001 + gac-api on :8766). That manual
install path is repeated on every new machine, and the worker fleet needs
a container image it can pull and mount its managed state directories
into. The data model (per-user XDG paths) already resolves every root
through XDG environment variables, which makes a single-mount container
footprint possible without code changes.

Two facts shape the image. First, the app derives the current user from
the config path: `<xdg_config>/agent-context/<user>/configs.yaml`. If an
ancestor directory is also named `agent-context`, a first-occurrence
match on the path returns the wrong segment (`.config`) and every
per-user path is built from a phantom user. The image user is therefore
named `gac`, not `agent-context`, and `_extract_user` matches the
innermost (last) occurrence of the app directory. Second, the app
authenticates against a users table that must exist before anyone can
log in, so the container needs a first-boot account path.

## Decision

We will ship an official Docker image built by GitHub Actions. The image
is python:3.12-slim + uv + make + tini; it installs the project from the
lockfile and runs `make serve`, so the container runs exactly what the
host runs. The container starts as root only long enough for an
entrypoint to normalize ownership of the mounted XDG directories to the
host user (PUID/PGID, the linuxserver convention the worker uses for
other containers such as comfyui) and then drops privileges via
setpriv before running the app as that user; the venv is frozen at build
time and UV_NO_SYNC is set so `uv run` never attempts a non-root
re-sync. The app runs with HOME=/home/gac, and the declaring service
mounts the worker's per-service pre-prepared directories onto that
user's four XDG roots. The Streamlit UI (:3001) and the API (:8766) are
both exposed -- both above 1024, so no root privileges are needed to
bind them. The API's /health endpoint is the container health probe.

The first account can be created two ways. By default no account is
created: the first user signs up through the UI. Alternatively, setting
GAC_BOOTSTRAP_USER and GAC_BOOTSTRAP_PASSWORD makes the entrypoint run
an idempotent bootstrap script (the `agent_context.users` API) as the
dropped user before the app starts. The bootstrap is opt-in and off when the
variables are unset. Because the bootstrap password lands in the
container environment (visible in `docker inspect`), it should be
rotated after first boot.

CI builds on main push, on tag push, and on manual dispatch. Main
builds tag the image `latest` and `sha-<short>` (per commit, so any main
commit is individually downloadable); tag builds add a versioned tag
matching the tag name. Both amd64 and arm64 are built on native runners
and combined into multi-arch manifests. Images are pushed to GHCR
(`ghcr.io/genesis-scaffolding/genesis-agent-context`, private).

## Status

Accepted

## Consequences

- A machine installs the system with `docker pull` + bind mounts, no
  clone, no uv, no Python toolchain.
- The four per-service mounts map the worker's pre-prepared directory
  layout 1:1 onto the app's data model, and the PUID/PGID entrypoint
  keeps every written file host-owned (no root-owned files in the
  volume).
- The image must keep the venv frozen at build time (UV_NO_SYNC);
  re-enabling syncs would break non-root startup, because the venv is
  root-owned.
- The image bakes in the `make serve` supervision model (tini + GNU
  Make -j 2). Replacing make would require reworking the image's
  entrypoint, but that is the app's existing runtime, not a new one.
- The image user is `gac`, not `agent-context`. The `_extract_user`
  innermost-match fix is the real fix for the shadowing hazard; the
  user name keeps the container out of the trap even if that patch is
  reverted.
- Builds depend on GHCR package permissions (GITHUB_TOKEN write
  access), which the repository's workflow permissions grant.
