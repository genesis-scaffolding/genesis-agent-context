"""Wire-shape Pydantic models for the agent API.

Datetime format: ``YYYY-MM-DDTHH:MM:SS.mmmZ`` (3-decimal, Z suffix).
Implemented as a shared Pydantic annotation so wire datetimes
serialise the same way everywhere.

Note on the journal wire model: the entity calls the calendar day
field ``date`` (see :class:`agent_context.journal.facade.Entry`). The wire
model also uses ``date`` for clarity. Because the field name
collides with the ``datetime.date`` class, we annotate with the
fully-qualified ``datetime.date`` everywhere.
"""

import datetime
from datetime import UTC
from datetime import datetime as _datetime
from typing import Annotated

from pydantic import BaseModel, Field, PlainSerializer

from ..journal.facade import EntryType
from ..profile import ProfileTarget

# ---------------------------------------------------------------------------
# Datetime serialization
# ---------------------------------------------------------------------------


def _format_utc_z(dt: _datetime) -> str:
    """Render a tz-aware datetime as ``YYYY-MM-DDTHH:MM:SS.mmmZ``."""
    utc = dt.astimezone(UTC)
    return utc.strftime("%Y-%m-%dT%H:%M:%S.") + f"{utc.microsecond // 1000:03d}Z"


UtcDateTime = Annotated[
    _datetime,
    PlainSerializer(lambda dt: _format_utc_z(dt), when_used="json"),
]


# ---------------------------------------------------------------------------
# Re-exports / wire enums
# ---------------------------------------------------------------------------


# Wire-side journal type re-exported as a string-valued alias.
# The entity's EntryType values (``memory | memory-synthesis | daily-handover``)
# are the wire values; no mapping is required.
JournalWireType = EntryType


# ---------------------------------------------------------------------------
# Journal
# ---------------------------------------------------------------------------


class JournalEntryCreateIn(BaseModel):
    type: JournalWireType
    date: datetime.date
    reference_date: datetime.date | None = None
    title: str | None = None
    content: str


class JournalEntryUpdateIn(BaseModel):
    title: str | None = None
    content: str | None = None


class JournalEntryOut(BaseModel):
    uid: str
    type: JournalWireType | None
    date: datetime.date
    reference_date: datetime.date | None
    title: str | None
    content: str
    created: UtcDateTime | None
    modified: UtcDateTime | None


class JournalListOut(BaseModel):
    items: list[JournalEntryOut]
    total: int
    offset: int
    limit: int


class JournalAppendIn(BaseModel):
    """Request body for POST /journals/{uid}/append."""

    content: str


class JournalSearchResultItemOut(BaseModel):
    """One result in a search response."""

    uid: str
    type: JournalWireType | None
    date: datetime.date
    title: str | None
    score: int
    snippet: str


class JournalSearchOut(BaseModel):
    """Response for GET /journals/search."""

    items: list[JournalSearchResultItemOut]
    total: int
    query: str


# ---------------------------------------------------------------------------
# Profile (ADR-025)
# ---------------------------------------------------------------------------


# Wire-side mirror of ProfileTarget. The enum values
# (``profile`` / ``life_story``) are the on-wire strings; the
# Python identifier is ``ProfileWireTarget`` to keep import lines
# short elsewhere.
ProfileWireTarget = ProfileTarget


class ProfileContentOut(BaseModel):
    """Read response: target + path + trimmed content."""

    target: ProfileWireTarget
    path: str
    content: str


class ProfileWriteIn(BaseModel):
    """Overwrite request body."""

    content: str
    note: str | None = None


class ProfileEditIn(BaseModel):
    """Surgical edit request body.

    ``global_replace`` replaces every occurrence; the default is
    first-only (matching the storage layer's contract). Empty
    ``old_text`` is rejected by the storage layer with a 400.
    """

    old_text: str
    new_text: str
    global_replace: bool = False
    note: str | None = None


class ProfileWriteOut(BaseModel):
    """Write / edit response: what was written + whether a snapshot was taken."""

    target: ProfileWireTarget
    path: str
    bytes_written: int
    replacements: int = 0
    snapshot: str | None = Field(
        default=None,
        description=("Filename of the snapshot taken after the write, or None when dedup skipped it."),
    )


class ProfileListRowOut(BaseModel):
    """One row of :class:`ProfileListOut`."""

    target: ProfileWireTarget
    path: str
    exists: bool
    bytes: int


class ProfileListOut(BaseModel):
    rows: list[ProfileListRowOut]
    profile_root: str


class ProfileSnapshotOut(BaseModel):
    """One history row."""

    ts: str
    filename: str
    sha: str | None
    size: int
    command: str | None
    note: str | None


class ProfileHistoryOut(BaseModel):
    target: ProfileWireTarget
    rows: list[ProfileSnapshotOut]
    total: int


class ProfileRestoreIn(BaseModel):
    """Restore request body."""

    version: str = Field(
        description=(
            "Snapshot identifier. Accepts the full UTC timestamp, a unique "
            "prefix of it, the bare .md filename, or the bare .meta.json filename. "
            "Errors on ambiguous prefix."
        ),
    )
    note: str | None = None


class ProfileRestoreOut(BaseModel):
    target: ProfileWireTarget
    applied_filename: str
    applied_size: int
    pre_restore_snapshot: str | None


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshIn(BaseModel):
    refresh_token: str
