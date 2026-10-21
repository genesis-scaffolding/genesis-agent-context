"""Regression tests for ``configs._extract_user``.

The extractor must find the user under the *innermost* ``agent-context``
directory. If an ancestor path component is also named after the app
(e.g. a home directory ``/home/agent-context``), a first-occurrence
match returns the wrong segment -- ``.config`` in that case -- and every
per-user path is then built from that phantom user.
"""

from __future__ import annotations

from pathlib import Path

from agent_context.configs import DEFAULT_USER, _extract_user, resolve_config_path


def test_extract_user_none_returns_default() -> None:
    assert _extract_user(None) == DEFAULT_USER


def test_extract_user_normal_host_path() -> None:
    p = Path("/home/gentran/.config/agent-context/gentran1991/configs.yaml")
    assert _extract_user(p) == "gentran1991"


def test_extract_user_default_user() -> None:
    p = Path("/home/gentran/.config/agent-context/default/configs.yaml")
    assert _extract_user(p) == "default"


def test_extract_user_app_named_home_dir() -> None:
    """Regression: a home directory named after the app must not shadow
    the app directory itself."""
    p = Path("/home/agent-context/.config/agent-context/gentran1991/configs.yaml")
    assert _extract_user(p) == "gentran1991"


def test_extract_user_app_named_home_dir_default_user() -> None:
    p = Path("/home/agent-context/.config/agent-context/default/configs.yaml")
    assert _extract_user(p) == "default"


def test_extract_user_legacy_flat_path() -> None:
    """Legacy flat path (~/.config/agent-context/configs.yaml) keeps working."""
    p = Path("/home/gentran/.config/agent-context/configs.yaml")
    assert _extract_user(p) == DEFAULT_USER


def test_extract_user_no_app_segment() -> None:
    p = Path("/home/gentran/.config/otherapp/gentran1991/configs.yaml")
    assert _extract_user(p) == DEFAULT_USER


def test_resolve_then_extract_round_trip_app_named_home(tmp_path: Path, monkeypatch) -> None:
    """End-to-end: resolve_config_path under an app-named config home
    must round-trip through _extract_user."""
    # Simulate a home directory named after the app, above the XDG config home.
    fake_home = tmp_path / "home" / "agent-context" / ".config"
    fake_home.mkdir(parents=True)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(fake_home))
    for user in ("gentran1991", "default", "exptest"):
        p = resolve_config_path(user)
        assert _extract_user(p) == user
