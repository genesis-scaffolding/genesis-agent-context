"""Console-script entry point for the agent API.

Usage:
    gac-api              # bind 0.0.0.0:8766
    GAC_API_PORT=9000 gac-api

Honors ``GAC_API_HOST`` and ``GAC_API_PORT``.
"""

from __future__ import annotations

import os

import uvicorn


def main() -> int:
    from .app import app

    host = os.environ.get("GAC_API_HOST", "0.0.0.0")
    port = int(os.environ.get("GAC_API_PORT", "8766"))
    uvicorn.run(app, host=host, port=port, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
