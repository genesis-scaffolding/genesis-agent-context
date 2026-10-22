"""Backup and restore for the signed in user's data.

The backup archive is a zip whose top level matches the on-disk layout
under ``<data_home>/<app_name>/``:

- ``MANIFEST.json`` at the root
- ``journals/...`` = ``<journal_root>/...``
- ``<user>/profile/...`` = the per-user profile directory
  (profile.md, protocol.md and their ``.versions`` snapshots;
  ADR-025)

Restore is destructive: it wipes the user's journal subtree and
profile subtree, then unpacks the archive into those locations. The
``import_from_bytes`` flow takes an automatic snapshot of the
current state first, so a bad restore is recoverable.
"""

from __future__ import annotations

import io
import json
import shutil
import zipfile
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from .manifest import MANIFEST_FILENAME, MANIFEST_SCHEMA_VERSION, Counts, Manifest

if TYPE_CHECKING:
    from ..core.facade import Facade

GENERATOR_TAG = "agent-context-backup"

_ARC_JOURNAL = "journals"
_ARC_PROFILE = "profile"


class ArchiveError(ValueError):
    """Raised when an archive is rejected by ``validate_archive`` or
    ``import_from_bytes``.
    """


class RestoreReport:
    """Counts and ancillary info returned by ``import_from_bytes``."""

    def __init__(
        self,
        *,
        journal: int,
        profile: int,
        safety_backup: Path | None,
    ) -> None:
        self.journal = journal
        self.profile = profile
        self.safety_backup = safety_backup


class ValidationReport:
    """Outcome of ``validate_archive``."""

    def __init__(
        self,
        *,
        manifest: Manifest | None,
        present_sections: set[str],
        issues: list[str],
    ) -> None:
        self.manifest = manifest
        self.present_sections = present_sections
        self.issues = issues

    @property
    def ok(self) -> bool:
        """True iff there are no issues. Manifest is non-null when ok."""
        return not self.issues and self.manifest is not None


class BackupFacade:
    """Backup and restore for the signed in user."""

    def __init__(self, parent: Facade) -> None:
        self._parent = parent  # type: ignore[arg-type]

    @property
    def _username(self) -> str:
        return str(self._parent.configs.user)

    @property
    def _journal_root(self) -> Path:
        return Path(self._parent.configs.paths.journal_root)

    @property
    def _journal_user_root(self) -> Path:
        """Path to this user's journal directory."""
        return self._journal_root / self._username

    @property
    def _profile_root(self) -> Path:
        """Path to this user's profile directory."""
        return Path(self._parent.configs.paths.profile_root)

    @property
    def _user_root(self) -> Path:
        """The per-user data directory that owns the profile root."""
        return self._profile_root.parent

    @property
    def _app_root(self) -> Path:
        """The per-app data root (``<data_home>/<app>``)."""
        return self._user_root.parent

    @property
    def _common_base(self) -> Path:
        """The shared parent of the journal and profile roots."""
        return self._app_root

    def _counts(self) -> Counts:
        """Snapshot counts."""
        journal_count = len(self._parent.journal.list_entries())
        profile_files = 0
        if self._profile_root.exists():
            profile_files = sum(1 for p in self._profile_root.rglob("*") if p.is_file())
        return Counts(
            journal=journal_count,
            profile=profile_files,
        )

    def _arcname_for(self, path: Path, base: Path) -> str:
        """Return the relative arcname for ``path`` against ``base``."""
        return path.relative_to(base).as_posix()

    def _iter_user_files(self) -> Iterator[tuple[Path, str]]:
        """Yield ``(absolute_path, arcname)`` for every file to archive."""
        base = self._common_base

        if self._journal_user_root.exists():
            for path in sorted(self._journal_user_root.rglob("*")):
                if path.is_file():
                    yield path, self._arcname_for(path, base)

        if self._profile_root.exists():
            if not self._profile_root.is_relative_to(self._user_root):
                raise ArchiveError(
                    f"profile_root ({self._profile_root}) is not under the user "
                    f"data root ({self._user_root}); cannot include it in the archive"
                )
            for path in sorted(self._profile_root.rglob("*")):
                if path.is_file():
                    yield path, self._arcname_for(path, self._app_root)

    def export_to_bytes(self) -> bytes:
        """Serialize the user's data to an in-memory zip."""
        manifest = Manifest(
            schema_version=MANIFEST_SCHEMA_VERSION,
            generator=GENERATOR_TAG,
            username=self._username,
            created_at=datetime.now(UTC),
            counts=self._counts(),
        )

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(MANIFEST_FILENAME, manifest.model_dump_json(indent=2))
            for absolute, arcname in self._iter_user_files():
                zf.write(absolute, arcname)
        return buffer.getvalue()

    def export_to_path(self, path: Path) -> None:
        """Write the archive to ``path``. Parent dirs are created."""
        data = self.export_to_bytes()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def validate_archive(self, data: bytes) -> ValidationReport:
        """Inspect an archive without mutating anything on disk."""
        issues: list[str] = []
        present_sections: set[str] = set()
        manifest: Manifest | None = None

        try:
            buffer = io.BytesIO(data)
            with zipfile.ZipFile(buffer, "r") as zf:
                names = zf.namelist()
                if MANIFEST_FILENAME not in names:
                    issues.append(f"missing {MANIFEST_FILENAME}")
                else:
                    try:
                        raw = json.loads(zf.read(MANIFEST_FILENAME).decode("utf-8"))
                        manifest = Manifest.model_validate(raw)
                    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                        issues.append(f"manifest is not valid JSON: {exc}")
                    except Exception as exc:
                        issues.append(f"manifest failed schema validation: {exc}")

                if manifest is not None:
                    if manifest.schema_version != MANIFEST_SCHEMA_VERSION:
                        issues.append(
                            f"schema_version {manifest.schema_version} is not supported "
                            f"(loader accepts {MANIFEST_SCHEMA_VERSION})"
                        )
                    if manifest.username != self._username:
                        issues.append(
                            f"archive belongs to user {manifest.username!r} but the "
                            f"signed in account is {self._username!r}"
                        )

                top_dirs = {n.split("/", 1)[0] for n in names if n and "/" in n}
                if _ARC_JOURNAL in top_dirs:
                    present_sections.add(_ARC_JOURNAL)
                if self._username in top_dirs:
                    present_sections.add(_ARC_PROFILE)
        except zipfile.BadZipFile as exc:
            issues.append(f"not a valid zip: {exc}")

        return ValidationReport(
            manifest=manifest,
            present_sections=present_sections,
            issues=issues,
        )

    def _safety_backup_path(self) -> Path:
        """Return the default location for the pre-restore snapshot."""
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        return self._common_base / f"pre-restore-{self._username}-{stamp}.zip"

    def _create_safety_backup(self, *, target_path: Path | None = None) -> Path | None:
        """Take a snapshot of the current state via ``export_to_bytes``."""
        snapshot_target = target_path or self._safety_backup_path()
        snapshot_target.parent.mkdir(parents=True, exist_ok=True)
        data = self.export_to_bytes()
        snapshot_target.write_bytes(data)
        return snapshot_target

    def _wipe_user_data(self) -> None:
        """Remove the user's journal and profile subtrees."""
        if self._journal_user_root.exists():
            shutil.rmtree(self._journal_user_root)
        if self._profile_root.exists():
            shutil.rmtree(self._profile_root)

    def _extract_archive(self, data: bytes) -> None:
        """Unpack the validated archive into the shared data directory."""
        base = self._common_base
        buffer = io.BytesIO(data)
        with zipfile.ZipFile(buffer, "r") as zf:
            for member in zf.infolist():
                if not member.filename or member.filename == MANIFEST_FILENAME:
                    continue
                target = (base / member.filename).resolve()
                if not target.is_relative_to(base.resolve()):
                    raise ArchiveError(f"archive entry {member.filename!r} would escape the shared data dir")
                target.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(member) as src, target.open("wb") as dst:
                    shutil.copyfileobj(src, dst)

    def import_from_bytes(self, data: bytes) -> RestoreReport:
        """Restore ``data`` into the signed in user's data scope."""
        report = self.validate_archive(data)
        if not report.ok:
            raise ArchiveError("; ".join(report.issues))

        snapshot_target = self._safety_backup_path()
        safety_path = self._create_safety_backup(target_path=snapshot_target)

        self._wipe_user_data()
        self._extract_archive(data)

        journal_count = len(self._parent.journal.list_entries())
        profile_count = 0
        if self._profile_root.exists():
            profile_count = sum(1 for p in self._profile_root.rglob("*") if p.is_file())

        return RestoreReport(
            journal=journal_count,
            profile=profile_count,
            safety_backup=safety_path,
        )

    def import_from_path(self, path: Path) -> RestoreReport:
        """Read ``path`` then delegate to :meth:`import_from_bytes`."""
        return self.import_from_bytes(path.read_bytes())
