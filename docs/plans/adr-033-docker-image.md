# Plan for adr-033

## Steps

1. Fix the stale Makefile: `run-cli` -> `uv run gac`, `ui` -> `uv run
   gac-ui` (the ASGI wrapper that mounts the session cookie routes),
   `api` -> `uv run gac-api`; `serve` keeps `$(MAKE) -j 2 ui api`.
2. Fix `_extract_user` in `src/agent_context/configs.py` to match the
   LAST occurrence of the app directory (innermost semantics) and
   update the stale docstring.
3. Add `tests/test_configs_user_extraction.py`: normal host path,
   default user, app-named home dir, app-named home dir + default user,
   legacy flat path, no app segment, and a `resolve_config_path` ->
   `_extract_user` round trip under an app-named config home.
4. Add `Dockerfile` (python:3.12-slim + uv + make + tini + curl;
   `uv sync --frozen`; frozen venv via UV_NO_SYNC=1; HOME=/home/gac;
   EXPOSE 3001 8766; healthcheck on :8766/health; tini entrypoint;
   `CMD make serve`).
5. Add `docker-entrypoint.sh`: root phase chowns the four XDG roots and
   the editable egg-info (conditionally, on the top dir's owner), then
   `exec setpriv --reuid --regid --clear-groups` drops to PUID/PGID.
6. Add `docker-bootstrap.sh`: opt-in first-boot account creation
   (`GAC_BOOTSTRAP_USER` / `GAC_BOOTSTRAP_PASSWORD`), idempotent, runs
   as the dropped user. Default is off; the first account comes from
   the UI sign-up form.
7. Add `.dockerignore` (git, venv, caches, tests, docs, .github).
8. Add `.github/workflows/docker-image.yml`: per-arch native builds on
   main push / tag push / manual dispatch, GHCR push, multi-arch
   manifest. Uses the `is_default_branch` metadata helper and renders
   the arch suffix with GitHub expressions (`${{ matrix.arch.suffix }}`),
   never metadata-action placeholders.
9. Add `docs/adr/adr-033-docker-image.md` and this plan.
10. Add `docker-build` / `docker-run` Makefile targets, ignore
    `.docker-data/`, and document both account paths plus the run
    command in the README.
11. (rev 2, non-root) The entrypoint became a drop-privilege entrypoint
    and the runtime identity moved from root to PUID/PGID (default
    1000/1000). The venv is frozen at build time so `uv run` never
    re-syncs the root-owned venv as a non-root user. The image user was
    named `gac` rather than `agent-context` so the config-path user
    extraction cannot be shadowed by an app-named home directory.
