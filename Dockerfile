# Container image for the agent-context system.
#
# Runs exactly what `make serve` runs on the host: the Streamlit UI on
# :3001 and the FastAPI server on :8766, supervised by tini so SIGTERM
# reaches both children. The container starts as root only long enough
# for the entrypoint to normalize ownership of the mounted XDG
# directories to the host user (PUID/PGID), then drops privileges via
# setpriv and runs the app as that user. Ports 3001 and 8766 are above
# 1024, so no root privileges are needed to bind them.
#
# The user's home is /home/gac; the declarative service mounts the
# per-service pre-prepared directories onto the user's four XDG roots.
# The image user is deliberately NOT named "agent-context": the user is
# derived from the config path, and an ancestor directory named after
# the app would shadow the real user segment (see ADR-033).

FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends make tini curl \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir uv

WORKDIR /app

# Lockfile + project metadata first for layer caching; the source second.
COPY pyproject.toml uv.lock ./
COPY src ./src
RUN uv sync --frozen --no-dev

COPY Makefile ./
COPY docker-entrypoint.sh docker-bootstrap.sh /app/
RUN chmod +x /app/docker-entrypoint.sh /app/docker-bootstrap.sh

# Default runtime identity (PUID/PGID default to this); the entrypoint
# re-chowns and re-drops to whatever PUID/PGID the service passes.
RUN useradd -u 1000 -m -d /home/gac gac

# The venv is frozen at build time; UV_NO_SYNC keeps `uv run` from
# attempting a re-sync at startup, which would fail as non-root on the
# root-owned /app/.venv.
ENV UV_NO_SYNC=1 \
    PATH="/app/.venv/bin:${PATH}" \
    HOME=/home/gac \
    XDG_CONFIG_HOME=/home/gac/.config \
    XDG_DATA_HOME=/home/gac/.local/share \
    XDG_STATE_HOME=/home/gac/.local/state \
    XDG_CACHE_HOME=/home/gac/.cache \
    GAC_UI_HOST=0.0.0.0 \
    GAC_UI_PORT=3001 \
    GAC_API_HOST=0.0.0.0 \
    GAC_API_PORT=8766

EXPOSE 3001 8766

HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=30s \
    CMD curl -fsS http://127.0.0.1:8766/health || exit 1

ENTRYPOINT ["/usr/bin/tini", "--", "/app/docker-entrypoint.sh"]
CMD ["make", "serve"]
