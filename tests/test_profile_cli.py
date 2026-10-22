"""CLI-level tests for the profile store commands.

Covers both surfaces the CLI exposes for the store:

- ``gac profile <cmd> <target>`` — the generic store interface, where
  ``<target>`` is ``profile`` (the persona) or ``protocol`` (the agent
  operating protocol).
- ``gac protocol <cmd>`` — the same operations pinned to the operating
  protocol.

The CLI reads and writes the local store through the ``Facade``, so
the tests point the XDG roots at a temp dir and assert on the files
that land on disk.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from agent_context.cli.app import app

runner = CliRunner()


@pytest.fixture
def store_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the XDG roots at a temp dir and return the profile root."""
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    return tmp_path / "data" / "agent-context" / "default" / "profile"


def _output(result) -> str:
    """Return stdout and stderr combined."""
    stderr = result.stderr
    if stderr is None:
        return result.output
    return result.output + stderr


def _snapshot_ts(result) -> list[str]:
    """Return the snapshot timestamps from a ``history`` listing, newest first.

    The listing is a header line, one line per snapshot, then a
    ``total N`` line.
    """
    lines = [line for line in result.output.splitlines() if line.strip()]
    rows = lines[1:-1]
    return [row.split()[0] for row in rows]


# ---------------------------------------------------------------------------
# gac profile list / read
# ---------------------------------------------------------------------------


def test_profile_list_shows_both_targets(store_root: Path):
    result = runner.invoke(app, ["profile", "list"])
    assert result.exit_code == 0, _output(result)
    assert "profile" in result.output
    assert "protocol" in result.output
    assert str(store_root / "profile.md") in result.output
    assert str(store_root / "protocol.md") in result.output


def test_profile_read_missing_file_exits_1(store_root: Path):
    result = runner.invoke(app, ["profile", "read", "profile"])
    assert result.exit_code == 1
    assert "does not exist" in _output(result)


def test_profile_read_unknown_target_exits_1(store_root: Path):
    result = runner.invoke(app, ["profile", "read", "persona"])
    assert result.exit_code == 1
    assert "Invalid profile target" in _output(result)


# ---------------------------------------------------------------------------
# gac profile write
# ---------------------------------------------------------------------------


def test_profile_write_then_read_round_trip(store_root: Path):
    result = runner.invoke(app, ["profile", "write", "profile", "--content", "I am a user\n"])
    assert result.exit_code == 0, _output(result)
    assert (store_root / "profile.md").read_text(encoding="utf-8") == "I am a user\n"

    result = runner.invoke(app, ["profile", "read", "profile"])
    assert result.exit_code == 0, _output(result)
    assert result.output.strip() == "I am a user"


def test_profile_write_protocol_target(store_root: Path):
    result = runner.invoke(app, ["profile", "write", "protocol", "--content", "rules\n"])
    assert result.exit_code == 0, _output(result)
    assert (store_root / "protocol.md").read_text(encoding="utf-8") == "rules\n"


def test_profile_write_from_file(store_root: Path, tmp_path: Path):
    source = tmp_path / "protocol.md"
    source.write_text("from a file\n", encoding="utf-8")
    result = runner.invoke(app, ["profile", "write", "protocol", "--content-file", str(source)])
    assert result.exit_code == 0, _output(result)
    assert (store_root / "protocol.md").read_text(encoding="utf-8") == "from a file\n"


def test_profile_write_from_file_alias(store_root: Path, tmp_path: Path):
    source = tmp_path / "protocol.md"
    source.write_text("alias\n", encoding="utf-8")
    result = runner.invoke(app, ["profile", "write", "protocol", "--file", str(source)])
    assert result.exit_code == 0, _output(result)
    assert (store_root / "protocol.md").read_text(encoding="utf-8") == "alias\n"


def test_profile_write_from_dash_file_reads_stdin(store_root: Path):
    result = runner.invoke(app, ["profile", "write", "protocol", "--content-file", "-"], input="dashed\n")
    assert result.exit_code == 0, _output(result)
    assert (store_root / "protocol.md").read_text(encoding="utf-8") == "dashed\n"


def test_profile_write_from_stdin(store_root: Path):
    result = runner.invoke(app, ["profile", "write", "protocol", "--stdin"], input="piped\n")
    assert result.exit_code == 0, _output(result)
    assert (store_root / "protocol.md").read_text(encoding="utf-8") == "piped\n"


def test_profile_write_requires_exactly_one_source(store_root: Path):
    result = runner.invoke(app, ["profile", "write", "protocol"])
    assert result.exit_code == 1
    assert "exactly one" in _output(result)


# ---------------------------------------------------------------------------
# gac profile edit / history / restore
# ---------------------------------------------------------------------------


def test_profile_edit_replaces_text(store_root: Path):
    runner.invoke(app, ["profile", "write", "protocol", "--content", "hello world\n"])
    result = runner.invoke(
        app,
        ["profile", "edit", "protocol", "--old", "world", "--new", "WORLD"],
    )
    assert result.exit_code == 0, _output(result)
    assert (store_root / "protocol.md").read_text(encoding="utf-8") == "hello WORLD\n"


def test_profile_edit_global_replace(store_root: Path):
    runner.invoke(app, ["profile", "write", "protocol", "--content", "foo foo foo\n"])
    result = runner.invoke(
        app,
        ["profile", "edit", "protocol", "--old", "foo", "--new", "bar", "--global-replace"],
    )
    assert result.exit_code == 0, _output(result)
    assert (store_root / "protocol.md").read_text(encoding="utf-8") == "bar bar bar\n"


def test_profile_edit_ambiguous_match_exits_1(store_root: Path):
    runner.invoke(app, ["profile", "write", "protocol", "--content", "foo foo\n"])
    result = runner.invoke(app, ["profile", "edit", "protocol", "--old", "foo", "--new", "bar"])
    assert result.exit_code == 1
    assert "matches 2 places" in _output(result)


def test_profile_edit_not_found_exits_1(store_root: Path):
    runner.invoke(app, ["profile", "write", "protocol", "--content", "hello\n"])
    result = runner.invoke(app, ["profile", "edit", "protocol", "--old", "nope", "--new", "x"])
    assert result.exit_code == 1
    assert "oldText not found" in _output(result)


def test_profile_history_lists_snapshots_newest_first(store_root: Path):
    runner.invoke(app, ["profile", "write", "protocol", "--content", "v1", "--note", "first"])
    runner.invoke(app, ["profile", "write", "protocol", "--content", "v2"])
    result = runner.invoke(app, ["profile", "history", "protocol"])
    assert result.exit_code == 0, _output(result)
    assert "first" in result.output
    assert "total 2" in result.output
    # Newest first: the snapshot carrying the note is the older one.
    rows = [line for line in result.output.splitlines() if line.strip()][1:-1]
    assert len(rows) == 2
    assert "first" in rows[1]
    assert "first" not in rows[0]


def test_profile_history_empty(store_root: Path):
    result = runner.invoke(app, ["profile", "history", "protocol"])
    assert result.exit_code == 0, _output(result)
    assert "(no snapshots)" in result.output


def test_profile_restore_round_trip(store_root: Path):
    runner.invoke(app, ["profile", "write", "protocol", "--content", "v1"])
    runner.invoke(app, ["profile", "write", "protocol", "--content", "v2"])
    history = runner.invoke(app, ["profile", "history", "protocol"])
    assert history.exit_code == 0, _output(history)
    ts = _snapshot_ts(history)[-1]

    result = runner.invoke(app, ["profile", "restore", "protocol", "--version", ts])
    assert result.exit_code == 0, _output(result)
    assert (store_root / "protocol.md").read_text(encoding="utf-8") == "v1"


def test_profile_restore_unknown_version_exits_1(store_root: Path):
    result = runner.invoke(app, ["profile", "restore", "protocol", "--version", "2099-99-99T000000000Z"])
    assert result.exit_code == 1
    assert "error" in _output(result)


# ---------------------------------------------------------------------------
# gac protocol (pinned to the operating protocol)
# ---------------------------------------------------------------------------


def test_protocol_write_then_read(store_root: Path):
    result = runner.invoke(app, ["protocol", "write", "--content", "operating rules\n"])
    assert result.exit_code == 0, _output(result)
    assert (store_root / "protocol.md").read_text(encoding="utf-8") == "operating rules\n"

    result = runner.invoke(app, ["protocol", "read"])
    assert result.exit_code == 0, _output(result)
    assert result.output.strip() == "operating rules"


def test_protocol_read_missing_exits_1(store_root: Path):
    result = runner.invoke(app, ["protocol", "read"])
    assert result.exit_code == 1
    assert "does not exist" in _output(result)


def test_protocol_edit(store_root: Path):
    runner.invoke(app, ["protocol", "write", "--content", "a b\n"])
    result = runner.invoke(app, ["protocol", "edit", "--old", "b", "--new", "c"])
    assert result.exit_code == 0, _output(result)
    assert (store_root / "protocol.md").read_text(encoding="utf-8") == "a c\n"


def test_protocol_history(store_root: Path):
    runner.invoke(app, ["protocol", "write", "--content", "v1"])
    result = runner.invoke(app, ["protocol", "history"])
    assert result.exit_code == 0, _output(result)
    assert "total 1" in result.output


def test_protocol_restore(store_root: Path):
    runner.invoke(app, ["protocol", "write", "--content", "v1"])
    runner.invoke(app, ["protocol", "write", "--content", "v2"])
    history = runner.invoke(app, ["protocol", "history"])
    assert history.exit_code == 0, _output(history)
    ts = _snapshot_ts(history)[-1]

    result = runner.invoke(app, ["protocol", "restore", "--version", ts])
    assert result.exit_code == 0, _output(result)
    assert (store_root / "protocol.md").read_text(encoding="utf-8") == "v1"


def test_protocol_group_does_not_touch_the_persona(store_root: Path):
    runner.invoke(app, ["protocol", "write", "--content", "rules\n"])
    assert not (store_root / "profile.md").exists()
    result = runner.invoke(app, ["profile", "read", "profile"])
    assert result.exit_code == 1
