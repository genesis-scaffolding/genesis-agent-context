"""Protocol endpoints: the agent operating protocol.

ADR-034. The operating protocol is a first-class entity of the
agent-context system (persona, protocol, memory), so it gets its own
pinned REST surface instead of only being reachable as
``/profile/protocol``:

- ``GET    /protocol``            read the protocol
- ``PUT    /protocol``            overwrite the protocol
- ``PATCH  /protocol``            surgical edit
- ``GET    /protocol/history``    list snapshots
- ``POST   /protocol/restore``    restore from snapshot

The semantics are identical to the matching ``/profile/protocol``
routes; both share the implementation in :mod:`._profile_ops` so the
two surfaces cannot drift.

Error mapping is the same as the profile router:

- File missing / empty   -> 404 (read)
- oldText empty / not found / matches N places -> 400 (edit)
- Version not found / ambiguous / none exist -> 400 (history, restore)
- Missing / bad token    -> 401 (auth dep)
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from ...profile import ProfileTarget
from ..auth import current_subject
from ..schemas import (
    ProfileContentOut,
    ProfileEditIn,
    ProfileHistoryOut,
    ProfileRestoreIn,
    ProfileRestoreOut,
    ProfileWriteIn,
    ProfileWriteOut,
)
from ._profile_ops import (
    edit_target,
    history_target,
    read_target,
    restore_target,
    write_target,
)

router = APIRouter(prefix="/protocol", tags=["protocol"])

TARGET = ProfileTarget.PROTOCOL
"""The target every route in this router operates on."""


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------


@router.get("", response_model=ProfileContentOut)
def read_protocol(
    subject: Annotated[str, Depends(current_subject)],
) -> ProfileContentOut:
    """Read the agent operating protocol (trimmed)."""
    return read_target(subject, TARGET)


# ---------------------------------------------------------------------------
# Write (overwrite)
# ---------------------------------------------------------------------------


@router.put("", response_model=ProfileWriteOut, status_code=status.HTTP_200_OK)
def write_protocol(
    body: ProfileWriteIn,
    subject: Annotated[str, Depends(current_subject)],
) -> ProfileWriteOut:
    """Overwrite the protocol. Creates a snapshot after success."""
    return write_target(subject, TARGET, body)


# ---------------------------------------------------------------------------
# Edit (surgical)
# ---------------------------------------------------------------------------


@router.patch("", response_model=ProfileWriteOut, status_code=status.HTTP_200_OK)
def edit_protocol(
    body: ProfileEditIn,
    subject: Annotated[str, Depends(current_subject)],
) -> ProfileWriteOut:
    """Replace ``old_text`` with ``new_text`` in the protocol.

    400 on empty ``old_text``, no match, or >1 match without
    ``global_replace``. 404 on missing protocol file. 200 on success.
    """
    return edit_target(subject, TARGET, body)


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------


@router.get("/history", response_model=ProfileHistoryOut)
def protocol_history(
    subject: Annotated[str, Depends(current_subject)],
    limit: Annotated[int | None, Query(ge=1, le=1000)] = None,
) -> ProfileHistoryOut:
    """List protocol snapshots (newest first).

    Optional ``limit`` caps the number of returned rows; the
    response ``total`` reports the unfiltered count.
    """
    return history_target(subject, TARGET, limit)


# ---------------------------------------------------------------------------
# Restore
# ---------------------------------------------------------------------------


@router.post("/restore", response_model=ProfileRestoreOut, status_code=status.HTTP_200_OK)
def protocol_restore(
    body: ProfileRestoreIn,
    subject: Annotated[str, Depends(current_subject)],
) -> ProfileRestoreOut:
    """Restore the protocol from snapshot ``version``.

    Snapshots the current protocol before applying the restore, so
    the restore is reversible.
    """
    return restore_target(subject, TARGET, body)
