"""Unit tests for ``agent_context.backup.facade.BackupFacade``."""

from __future__ import annotations

import json
import zipfile
from datetime import date as date_cls
from datetime import datetime
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from agent_context.backup import (
    MANIFEST_SCHEMA_VERSION,
    BackupFacade,
    RestoreReport,
)
from agent_context.core.facade import Facade
from agent_context.journal.facade import Entry, EntryType, JournalFacade


@pytest.fixture
def layout(tmp_path: Path) -> SimpleNamespace:
    """Set up the shared data dir + journals + profile."""
    common = tmp_path / "data" / "agent-context"
    jrn_root = common / "journals"
    jrn_root.mkdir(parents=True)

    username = "alice"
    jrn_user = jrn_root / username
    jrn_user.mkdir()

    profile_root = common / username / "profile"
    profile_root.mkdir(parents=True)
    (profile_root / "profile.md").write_text("# Profile\n\nAlice's profile.\n")

    return SimpleNamespace(
        common=common,
        jrn_root=jrn_root,
        jrn_user=jrn_user,
        profile_root=profile_root,
        username=username,
    )


@pytest.fixture
def backup(layout: SimpleNamespace) -> BackupFacade:
    """Construct a :class:`BackupFacade` over a controlled tmp dir."""
    journal_entries = [
        Entry(
            date=date_cls(2026, 9, 1),
            title="Day one",
            type=EntryType.MEMORY,
            content="First entry\n",
        ),
        Entry(
            date=date_cls(2026, 9, 2),
            title="Day two",
            type=EntryType.MEMORY,
            content="Second entry\n",
        ),
    ]

    class _MockFacade:
        class _configs:
            user = layout.username
            paths = SimpleNamespace(
                journal_root=layout.jrn_root,
                profile_root=layout.profile_root,
            )

        configs = _configs()

        def __init__(self) -> None:
            self.journal = JournalFacade(layout.jrn_user)
            for e in journal_entries:
                self.journal.save_entry(e)

    return BackupFacade(cast(Facade, _MockFacade()))


def test_export_manifest_schema_version(backup: BackupFacade) -> None:
    """``export_to_bytes`` produces a valid manifest with the current schema version."""
    data = backup.export_to_bytes()
    buffer = BytesIO(data)
    with zipfile.ZipFile(buffer, "r") as zf:
        manifest_raw = json.loads(zf.read("MANIFEST.json").decode())
    assert manifest_raw["schema_version"] == MANIFEST_SCHEMA_VERSION


def test_export_journals_present(backup: BackupFacade, layout: SimpleNamespace) -> None:
    """Export zip contains journal entries for the user."""
    data = backup.export_to_bytes()
    buffer = BytesIO(data)
    with zipfile.ZipFile(buffer, "r") as zf:
        names = zf.namelist()
    usernames_in_arc = {n.split("/")[1] for n in names if n.startswith("journals/")}
    assert layout.username in usernames_in_arc


def test_export_profile_present(backup: BackupFacade, layout: SimpleNamespace) -> None:
    """Export zip contains the user's profile directory."""
    data = backup.export_to_bytes()
    buffer = BytesIO(data)
    with zipfile.ZipFile(buffer, "r") as zf:
        names = zf.namelist()
    assert any(layout.username in n for n in names)


def test_validate_archive_ok(backup: BackupFacade) -> None:
    """Valid archive passes validation."""
    data = backup.export_to_bytes()
    report = backup.validate_archive(data)
    assert report.ok


def test_validate_archive_wrong_user(layout: SimpleNamespace, backup: BackupFacade) -> None:
    """Archive belonging to a different user is rejected."""
    manifest_data = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "generator": "test",
        "username": "bob",
        "created_at": datetime.now().isoformat(),
        "counts": {"journal": 0, "profile": 0},
    }
    bad_buffer = BytesIO()
    with zipfile.ZipFile(bad_buffer, "w") as zf:
        zf.writestr("MANIFEST.json", json.dumps(manifest_data))
    report = backup.validate_archive(bad_buffer.getvalue())
    assert not report.ok
    assert any("bob" in issue for issue in report.issues)


def test_validate_archive_bad_zip() -> None:
    """Non-zip data is rejected."""
    facade = cast(Facade, object())  # dummy
    bf = BackupFacade(facade)
    report = bf.validate_archive(b"not a zip")
    assert not report.ok
    assert any("not a valid zip" in i for i in report.issues)


def test_import_round_trip(layout: SimpleNamespace, backup: BackupFacade) -> None:
    """Export then import produces the same journal entries and profile."""
    data = backup.export_to_bytes()

    # Wipe the user's dirs
    import shutil

    shutil.rmtree(layout.jrn_user)
    shutil.rmtree(layout.profile_root)

    report = backup.import_from_bytes(data)
    assert isinstance(report, RestoreReport)
    assert report.safety_backup is not None

    # Verify journals round-tripped
    fresh_journal = JournalFacade(layout.jrn_user)
    entries = fresh_journal.list_entries()
    assert len(entries) == 2
    titles = {e.title for e in entries}
    assert titles == {"Day one", "Day two"}

    # Verify profile round-tripped
    assert (layout.profile_root / "profile.md").exists()
    content = (layout.profile_root / "profile.md").read_text()
    assert "Profile" in content
