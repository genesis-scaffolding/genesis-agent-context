"""HTTP-level tests for the /journals endpoints.

Drives the full FastAPI app via ``TestClient``. Journal storage is
plain markdown files, so these tests run fast and do not need to be
marked ``integration``.

The point of this file is route reachability: ``GET /journals/resolve``
and ``GET /journals/search`` are literal paths that must be declared
before ``GET /journals/{uid}``, otherwise Starlette matches them as
``uid`` literals and they 404 for every caller.
"""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from agent_context.api.app import app
from agent_context.users.store import UserStore

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def journals_client(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[TestClient, None, None]:
    """Yield a TestClient with one user and a clean journal root."""
    state_dir = tmp_path / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    users_path = state_dir / "users.yaml"
    UserStore(users_path).add("default", "test-pw")
    monkeypatch.setattr("agent_context.users.store._default_store", UserStore(users_path))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("XDG_STATE_HOME", str(state_dir))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    with TestClient(app) as client:
        yield client


@pytest.fixture
def auth(journals_client: TestClient) -> dict[str, str]:
    """Default-user bearer headers."""
    resp = journals_client.post(
        "/auth/login",
        data={"username": "default", "password": "test-pw", "grant_type": "password"},
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _create(client: TestClient, auth: dict[str, str], **body: object) -> dict[str, object]:
    """Create a journal entry and return the wire body."""
    resp = client.post("/journals", headers=auth, json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# /journals/{uid} still works
# ---------------------------------------------------------------------------


def test_read_by_uid_still_works(journals_client, auth):
    created = _create(
        journals_client,
        auth,
        type="memory",
        date="2026-10-20",
        title="Note",
        content="body text",
    )
    r = journals_client.get(f"/journals/{created['uid']}", headers=auth)
    assert r.status_code == 200
    assert r.json()["uid"] == created["uid"]


# ---------------------------------------------------------------------------
# /journals/resolve
# ---------------------------------------------------------------------------


def test_resolve_returns_memory_entry(journals_client, auth):
    created = _create(
        journals_client,
        auth,
        type="memory",
        date="2026-10-20",
        title="Note",
        content="body text",
    )
    r = journals_client.get("/journals/resolve", headers=auth, params={"type": "memory", "date": "2026-10-20"})
    assert r.status_code == 200, r.text
    assert r.json()["uid"] == created["uid"]
    assert r.json()["content"] == "body text"


def test_resolve_prefers_synthesis(journals_client, auth):
    _create(journals_client, auth, type="memory", date="2026-10-20", content="raw")
    synth = _create(journals_client, auth, type="memory-synthesis", date="2026-10-20", content="synthesised")
    r = journals_client.get("/journals/resolve", headers=auth, params={"type": "memory", "date": "2026-10-20"})
    assert r.status_code == 200, r.text
    assert r.json()["uid"] == synth["uid"]


def test_resolve_missing_date_returns_404(journals_client, auth):
    r = journals_client.get("/journals/resolve", headers=auth, params={"type": "memory", "date": "2020-01-01"})
    assert r.status_code == 404


def test_resolve_rejects_unknown_type(journals_client, auth):
    r = journals_client.get("/journals/resolve", headers=auth, params={"type": "daily", "date": "2026-10-20"})
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# /journals/search
# ---------------------------------------------------------------------------


def test_search_returns_scored_results(journals_client, auth):
    created = _create(
        journals_client,
        auth,
        type="memory",
        date="2026-10-20",
        title="kubernetes rollout",
        content="the kubernetes rollout failed twice",
    )
    r = journals_client.get("/journals/search", headers=auth, params={"q": "kubernetes"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["query"] == "kubernetes"
    assert body["total"] == 1
    assert body["items"][0]["uid"] == created["uid"]
    assert body["items"][0]["score"] > 0


def test_search_with_no_hits_returns_empty_list(journals_client, auth):
    _create(journals_client, auth, type="memory", date="2026-10-20", content="unrelated")
    r = journals_client.get("/journals/search", headers=auth, params={"q": "kubernetes"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] == 0
    assert body["items"] == []


def test_search_filters_by_type(journals_client, auth):
    _create(journals_client, auth, type="memory", date="2026-10-20", content="kubernetes notes")
    _create(journals_client, auth, type="daily-handover", date="2026-10-20", content="kubernetes handover")
    r = journals_client.get("/journals/search", headers=auth, params={"q": "kubernetes", "type": "memory"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] == 1
    assert body["items"][0]["type"] == "memory"


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


def test_resolve_requires_auth(journals_client):
    r = journals_client.get("/journals/resolve", params={"type": "memory", "date": "2026-10-20"})
    assert r.status_code == 401


def test_search_requires_auth(journals_client):
    r = journals_client.get("/journals/search", params={"q": "kubernetes"})
    assert r.status_code == 401
