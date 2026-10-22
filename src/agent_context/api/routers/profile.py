"""Profile endpoints: per-user profile and protocol markdown store.

ADR-025, ADR-034. Six endpoints under ``/profile``:

- ``GET    /profile``                  list both targets
- ``GET    /profile/{target}``         read
- ``PUT    /profile/{target}``         overwrite
- ``PATCH  /profile/{target}``         surgical edit
- ``GET    /profile/{target}/history`` list snapshots
- ``POST   /profile/{target}/restore`` restore from snapshot

``{target}`` accepts ``profile`` (the persona) and ``protocol`` (the
agent operating protocol). The protocol also has its own pinned
surface under ``/protocol`` (see :mod:`.protocol`); both routers
share the implementation in :mod:`._profile_ops`.

The handler builds a :class:`ProfileFacade` from the JWT subject
on every request so one token can only touch one user's data.
There is no cross-user API.

Error mapping (storage layer returns ``ok=False`` results; we
translate to 4xx):

- File missing / empty   -> 404 (read)
- oldText empty / not found / matches N places -> 400 (edit)
- Unknown target         -> 404 (path param)
- Version not found / ambiguous / none exist -> 400 (history, restore)
- Missing / bad token    -> 401 (auth dep)
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ...profile import ProfileTarget, parse_target
from ..auth import current_subject
from ..schemas import (
    ProfileContentOut,
    ProfileEditIn,
    ProfileHistoryOut,
    ProfileListOut,
    ProfileListRowOut,
    ProfileRestoreIn,
    ProfileRestoreOut,
    ProfileWireTarget,
    ProfileWriteIn,
    ProfileWriteOut,
)
from ._profile_ops import (
    edit_target,
    facade_for,
    history_target,
    read_target,
    restore_target,
    write_target,
)

router = APIRouter(prefix="/profile", tags=["profile"])


def _parse_target_path_param(target: str) -> ProfileTarget:
    """Validate the ``{target}`` path segment."""
    try:
        return parse_target(target)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------


@router.get("", response_model=ProfileListOut)
def list_profiles(
    subject: Annotated[str, Depends(current_subject)],
) -> ProfileListOut:
    """List both profile targets with active path + existence + size."""
    facade = facade_for(subject)
    try:
        listed = facade.profile.list()
        return ProfileListOut(
            rows=[
                ProfileListRowOut(
                    target=ProfileWireTarget(row.target.value),
                    path=row.path,
                    exists=row.exists,
                    bytes=row.bytes,
                )
                for row in listed.rows
            ],
            profile_root=listed.profile_root,
        )
    finally:
        facade.shutdown()


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------


@router.get("/{target}", response_model=ProfileContentOut)
def read_profile(
    target: str,
    subject: Annotated[str, Depends(current_subject)],
) -> ProfileContentOut:
    """Read the canonical content for ``target`` (trimmed)."""
    parsed = _parse_target_path_param(target)
    return read_target(subject, parsed)


# ---------------------------------------------------------------------------
# Write (overwrite)
# ---------------------------------------------------------------------------


@router.put("/{target}", response_model=ProfileWriteOut, status_code=status.HTTP_200_OK)
def write_profile(
    target: str,
    body: ProfileWriteIn,
    subject: Annotated[str, Depends(current_subject)],
) -> ProfileWriteOut:
    """Overwrite the canonical file. Creates a snapshot after success."""
    parsed = _parse_target_path_param(target)
    return write_target(subject, parsed, body)


# ---------------------------------------------------------------------------
# Edit (surgical)
# ---------------------------------------------------------------------------


@router.patch("/{target}", response_model=ProfileWriteOut, status_code=status.HTTP_200_OK)
def edit_profile(
    target: str,
    body: ProfileEditIn,
    subject: Annotated[str, Depends(current_subject)],
) -> ProfileWriteOut:
    """Replace ``old_text`` with ``new_text`` in the canonical file.

    400 on empty ``old_text``, no match, or >1 match without
    ``global_replace``. 404 on missing target file. 200 on success
    (with the snapshot filename if a snapshot was taken).
    """
    parsed = _parse_target_path_param(target)
    return edit_target(subject, parsed, body)


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------


@router.get("/{target}/history", response_model=ProfileHistoryOut)
def profile_history(
    target: str,
    subject: Annotated[str, Depends(current_subject)],
    limit: Annotated[int | None, Query(ge=1, le=1000)] = None,
) -> ProfileHistoryOut:
    """List snapshots for ``target`` (newest first).

    Optional ``limit`` caps the number of returned rows; the
    response ``total`` reports the unfiltered count.
    """
    parsed = _parse_target_path_param(target)
    return history_target(subject, parsed, limit)


# ---------------------------------------------------------------------------
# Restore
# ---------------------------------------------------------------------------


@router.post("/{target}/restore", response_model=ProfileRestoreOut, status_code=status.HTTP_200_OK)
def profile_restore(
    target: str,
    body: ProfileRestoreIn,
    subject: Annotated[str, Depends(current_subject)],
) -> ProfileRestoreOut:
    """Restore ``target`` from snapshot ``version``.

    Snapshots the current canonical file before applying the
    restore, so the restore is reversible.
    """
    parsed = _parse_target_path_param(target)
    return restore_target(subject, parsed, body)
