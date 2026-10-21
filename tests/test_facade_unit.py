"""Unit tests for ``agent_context.core.facade.Facade``."""

from __future__ import annotations

from pathlib import Path

import pytest

from agent_context.core.facade import Facade


def test_facade_constructs_with_default_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Facade constructs without error when no config file exists."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))

    facade = Facade(ensure_server=False)
    assert facade.configs.app_name == "agent-context"
    facade.shutdown()


def test_facade_exposes_journal_and_profile(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Facade exposes journal and profile properties."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    facade = Facade(ensure_server=False)
    _ = facade.journal
    _ = facade.profile
    facade.shutdown()
