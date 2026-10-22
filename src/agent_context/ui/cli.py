"""Console-script entry point for the Streamlit UI.

Usage:
    gac-ui              # bind 0.0.0.0:3001
    GAC_UI_PORT=9000 gac-ui

Honors ``GAC_UI_HOST`` and ``GAC_UI_PORT``.

This module used to live in ``agent_context.cli.app`` alongside the
agent-facing Typer CLI. The CLI now ships separately (my-agent-skills
repo); only the UI launcher stays in this package.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from ..configs import CONFIG_PATH_ENV, DEFAULT_USER, resolve_config_path


def main_ui() -> int:
    """Start Streamlit for the default user.

    Honors ``GAC_UI_PORT`` (default 3001) and ``GAC_UI_HOST``
    (default 0.0.0.0).

    Implementation note: this entry point ``execvp``s into ``streamlit
    run`` rather than spawning it as a subprocess. The previous
    ``subprocess.call`` approach added a Python wrapper layer between
    the shell and streamlit; when the shell sent SIGINT to its
    process group (``kill 0``), the wrapper died but the streamlit
    process was reparented to PID 1 and stopped responding to the
    signal, leaving bash's ``wait`` blocked. Replacing the wrapper
    with streamlit keeps the process tree flat, so signals reach
    streamlit directly.
    """
    config_path = resolve_config_path(DEFAULT_USER)
    os.environ[CONFIG_PATH_ENV] = str(config_path.resolve())

    # Run the ASGI wrapper (not app.py directly) so the
    # /api/session/{login,logout} cookie routes are mounted —
    # the auth forms' JS fetches those endpoints to persist the
    # session cookie (ADR-021).
    app_path = Path(__file__).resolve().parent / "asgi_app.py"
    port = os.environ.get("GAC_UI_PORT", "3001")
    host = os.environ.get("GAC_UI_HOST", "0.0.0.0")

    argv = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(app_path),
        "--server.address",
        host,
        "--server.port",
        str(port),
        "--server.headless",
        "true",
    ]
    os.execvp(sys.executable, argv)
    return 1


if __name__ == "__main__":
    raise SystemExit(main_ui())
