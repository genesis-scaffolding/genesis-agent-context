"""Shared test fixtures for genesis-agent-context.

Most tests are self-contained (journal/profile units use tmp_path
directly; test_profile_api.py defines its own client fixture).
This conftest keeps only the small shared helpers.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from agent_context.users.store import UserStore


@pytest.fixture
def user_store(tmp_path: Path) -> UserStore:
    """A fresh UserStore backed by a temp users.yaml."""
    return UserStore(tmp_path / "users.yaml")
