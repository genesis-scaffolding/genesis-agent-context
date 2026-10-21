"""FastAPI application for the agent-context API.

Wires up CORS, the auth router, the journals router, and the profile
router under a single ``app`` instance. ``agent_context.api.cli`` runs this
with ``uvicorn``.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .auth import router as auth_router
from .routers.journals import router as journals_router
from .routers.profile import router as profile_router

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    app = FastAPI(
        title="Agent Context API",
        description=(
            "REST API for the agent context system (persona, memory, and handover stores). "
            "Authentication: OAuth2 password grant with bearer tokens."
        ),
        version="0.1.0",
    )

    # Loopback-only CORS in v1.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost",
            "http://127.0.0.1",
            "http://localhost:3001",
            "http://127.0.0.1:3001",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", tags=["health"])
    def health() -> dict[str, str]:
        return {"status": "online"}

    app.include_router(auth_router)
    app.include_router(journals_router)
    app.include_router(profile_router)

    return app


app = create_app()
