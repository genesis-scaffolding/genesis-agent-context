"""Shared profile-store operations for the profile and protocol routers.

Both routers expose the same store (``facade.profile``). They differ
only in how the target is chosen:

- the profile router takes it from the ``{target}`` path segment,
- the protocol router pins it to :attr:`ProfileTarget.PROTOCOL`.

The logic lives here so the two surfaces cannot drift. Every function
builds a fresh :class:`Facade` from the JWT subject, so one token can
only touch one user's data. There is no cross-user API.

Error mapping (the storage layer returns ``ok=False`` results; we
translate to 4xx):

- File missing / empty   -> 404 (read)
- oldText empty / not found / matches N places -> 400 (edit)
- Version not found / ambiguous / none exist -> 400 (history, restore)
"""

from __future__ import annotations

from fastapi import HTTPException

from ...configs import resolve_config_path
from ...core.facade import Facade
from ...profile import ProfileTarget
from ..schemas import (
    ProfileContentOut,
    ProfileEditIn,
    ProfileHistoryOut,
    ProfileRestoreIn,
    ProfileRestoreOut,
    ProfileSnapshotOut,
    ProfileWireTarget,
    ProfileWriteIn,
    ProfileWriteOut,
)


def facade_for(subject: str) -> Facade:
    """Build a per-request :class:`Facade` for ``subject``.

    Same pattern as the journals router: a fresh facade per request,
    scoped to the JWT subject. Only ``facade.profile`` is used here;
    the rest of the Facade (journal, backup, ...) is constructed
    lazily and never reached.
    """
    return Facade(resolve_config_path(subject))


def snapshot_filename(snap) -> str | None:
    """Render the snapshot filename (None when the snapshot was dedup-skipped)."""
    if snap is None or not snap.ok:
        return None
    return snap.filename


def wire_target(target: ProfileTarget | None, fallback: ProfileTarget) -> ProfileWireTarget:
    """Return the wire target, falling back when the result carries none."""
    return ProfileWireTarget(target.value if target is not None else fallback.value)


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------


def read_target(subject: str, target: ProfileTarget) -> ProfileContentOut:
    """Read the canonical content for ``target`` (trimmed)."""
    facade = facade_for(subject)
    try:
        result = facade.profile.read(target)
        if not result.ok:
            # File missing or empty: 404.
            raise HTTPException(status_code=404, detail=result.error)
        return ProfileContentOut(
            target=wire_target(result.target, target),
            path=result.path,
            content=result.content,
        )
    finally:
        facade.shutdown()


# ---------------------------------------------------------------------------
# Write (overwrite)
# ---------------------------------------------------------------------------


def write_target(subject: str, target: ProfileTarget, body: ProfileWriteIn) -> ProfileWriteOut:
    """Overwrite the canonical file. Creates a snapshot after success."""
    facade = facade_for(subject)
    try:
        result = facade.profile.write(target, body.content, note=body.note)
        if not result.ok:
            raise HTTPException(status_code=500, detail=result.error)
        return ProfileWriteOut(
            target=wire_target(result.target, target),
            path=result.path,
            bytes_written=result.bytes_written,
            snapshot=snapshot_filename(result.snapshot),
        )
    finally:
        facade.shutdown()


# ---------------------------------------------------------------------------
# Edit (surgical)
# ---------------------------------------------------------------------------


def edit_target(subject: str, target: ProfileTarget, body: ProfileEditIn) -> ProfileWriteOut:
    """Replace ``old_text`` with ``new_text`` in the canonical file.

    400 on empty ``old_text``, no match, or >1 match without
    ``global_replace``. 404 on missing target file. 200 on success
    (with the snapshot filename if a snapshot was taken).
    """
    facade = facade_for(subject)
    try:
        result = facade.profile.edit(
            target,
            body.old_text,
            body.new_text,
            global_replace=body.global_replace,
            note=body.note,
        )
        if not result.ok:
            # Storage-layer errors are user mistakes (empty / not
            # found / ambiguous). 500 is reserved for actual bugs.
            err = result.error
            if "oldText is empty" in err or "oldText not found" in err or "matches" in err:
                raise HTTPException(status_code=400, detail=err)
            if "does not exist" in err:
                raise HTTPException(status_code=404, detail=err)
            raise HTTPException(status_code=500, detail=err)
        return ProfileWriteOut(
            target=wire_target(result.target, target),
            path=result.path,
            bytes_written=result.bytes_written,
            replacements=result.replacements,
            snapshot=snapshot_filename(result.snapshot),
        )
    finally:
        facade.shutdown()


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------


def history_target(subject: str, target: ProfileTarget, limit: int | None) -> ProfileHistoryOut:
    """List snapshots for ``target`` (newest first).

    ``limit`` caps the number of returned rows; the response ``total``
    reports the unfiltered count.
    """
    facade = facade_for(subject)
    try:
        result = facade.profile.history(target, limit=limit)
        if not result.ok:
            raise HTTPException(status_code=500, detail=result.error)
        rows = [
            ProfileSnapshotOut(
                ts=row.ts,
                filename=row.filename,
                sha=row.meta.this_sha[:12] if row.meta is not None else None,
                size=row.size,
                command=row.meta.command if row.meta is not None else None,
                note=row.meta.note if row.meta is not None else None,
            )
            for row in result.snapshots
        ]
        return ProfileHistoryOut(
            target=wire_target(result.target, target),
            rows=rows,
            total=result.total,
        )
    finally:
        facade.shutdown()


# ---------------------------------------------------------------------------
# Restore
# ---------------------------------------------------------------------------


def restore_target(subject: str, target: ProfileTarget, body: ProfileRestoreIn) -> ProfileRestoreOut:
    """Restore ``target`` from snapshot ``version``.

    Snapshots the current canonical file before applying the restore,
    so the restore is reversible.
    """
    facade = facade_for(subject)
    try:
        result = facade.profile.restore(target, body.version, note=body.note)
        if not result.ok:
            err = result.error
            if "No snapshots exist" in err or "matches prefix" in err or "matches" in err:
                raise HTTPException(status_code=400, detail=err)
            raise HTTPException(status_code=500, detail=err)
        return ProfileRestoreOut(
            target=wire_target(result.target, target),
            applied_filename=result.applied_filename,
            applied_size=result.applied_size,
            pre_restore_snapshot=snapshot_filename(result.pre_restore_snapshot),
        )
    finally:
        facade.shutdown()


__all__ = [
    "edit_target",
    "facade_for",
    "history_target",
    "read_target",
    "restore_target",
    "snapshot_filename",
    "wire_target",
    "write_target",
]
