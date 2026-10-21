"""Journal endpoints: list, read, create, update, delete.

The journal facade stores entries as markdown files. No project or
task integration in this stripped-down router.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ...configs import resolve_config_path
from ...core.facade import Facade
from ...journal.facade import Entry, EntryType
from ..auth import current_subject
from ..schemas import (
    JournalEntryCreateIn,
    JournalEntryOut,
    JournalEntryUpdateIn,
    JournalListOut,
)

router = APIRouter(prefix="/journals", tags=["journals"])


def _facade(subject: str) -> Facade:
    """Build a per-request :class:`Facade` for ``subject``."""
    return Facade(resolve_config_path(subject))


def _journal_to_wire(entry: Entry) -> JournalEntryOut:
    """Convert a journal Entry to the wire model."""
    return JournalEntryOut(
        uid=entry.uid,
        type=entry.type,
        date=entry.date,
        reference_date=entry.reference_date,
        title=entry.title,
        content=entry.content,
        created=entry.created,
        modified=entry.modified,
    )


def _paginate[T](
    items: list[T],
    offset: int | None,
    limit: int | None,
) -> tuple[list[T], int, int, int]:
    """Slice ``items`` for the response and return ``(slice, total, offset, limit)``."""
    effective_offset = offset if offset is not None else 0
    total = len(items)
    if limit is not None:
        page = items[effective_offset : effective_offset + limit]
        return page, total, effective_offset, limit
    page = items[effective_offset:]
    return page, total, effective_offset, total - effective_offset


@router.get("", response_model=JournalListOut)
def list_journals(
    subject: Annotated[str, Depends(current_subject)],
    entry_type: Annotated[str | None, Query(alias="type")] = None,
    search_query: Annotated[str | None, Query()] = None,
    reference_date_start: Annotated[str | None, Query(alias="date_start")] = None,
    reference_date_end: Annotated[str | None, Query(alias="date_end")] = None,
    sort_by: Annotated[list[str] | None, Query()] = None,
    order: Annotated[str, Query()] = "desc",
    offset: Annotated[int | None, Query()] = None,
    limit: Annotated[int, Query()] = 50,
) -> JournalListOut:
    facade = _facade(subject)
    try:
        all_entries = facade.journal.list_entries()

        if entry_type:
            try:
                wanted = EntryType(entry_type)
            except ValueError as e:
                raise HTTPException(status_code=400, detail=f"unknown entry_type: {entry_type}") from e
            all_entries = [e for e in all_entries if e.type == wanted]

        if reference_date_start:
            start = datetime.fromisoformat(reference_date_start).date()
            all_entries = [
                e for e in all_entries if (e.reference_date if e.reference_date is not None else e.date) >= start
            ]
        if reference_date_end:
            end = datetime.fromisoformat(reference_date_end).date()
            all_entries = [
                e for e in all_entries if (e.reference_date if e.reference_date is not None else e.date) <= end
            ]

        if search_query:
            needle = search_query.lower()
            all_entries = [
                e
                for e in all_entries
                if (e.title and needle in e.title.lower()) or needle in e.content.lower()
            ]

        all_wire = [_journal_to_wire(e) for e in all_entries]
        page, total, offset, limit = _paginate(all_wire, offset, limit)
        return JournalListOut(
            items=page,
            total=total,
            offset=offset,
            limit=limit,
        )
    finally:
        facade.shutdown()


@router.post("", response_model=JournalEntryOut, status_code=status.HTTP_201_CREATED)
def create_journal(
    body: JournalEntryCreateIn,
    subject: Annotated[str, Depends(current_subject)],
) -> JournalEntryOut:
    facade = _facade(subject)
    try:
        entry = Entry(
            date=body.date,
            reference_date=body.reference_date,
            title=body.title,
            type=body.type,
            content=body.content,
        )
        try:
            facade.journal.save_entry(entry)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        saved = facade.journal.get_entry(entry.uid)
        if saved is None:
            raise HTTPException(status_code=500, detail="Failed to read back created entry")
        return _journal_to_wire(saved)
    finally:
        facade.shutdown()


@router.get("/{uid}", response_model=JournalEntryOut)
def read_journal(
    uid: str,
    subject: Annotated[str, Depends(current_subject)],
) -> JournalEntryOut:
    facade = _facade(subject)
    try:
        entry = facade.journal.get_entry(uid)
        if entry is None:
            raise HTTPException(status_code=404, detail="Journal entry not found")
        return _journal_to_wire(entry)
    finally:
        facade.shutdown()


@router.patch("/{uid}", response_model=JournalEntryOut)
def update_journal(
    uid: str,
    body: JournalEntryUpdateIn,
    subject: Annotated[str, Depends(current_subject)],
) -> JournalEntryOut:
    facade = _facade(subject)
    try:
        existing = facade.journal.get_entry(uid)
        if existing is None:
            raise HTTPException(status_code=404, detail="Journal entry not found")

        title = body.title if body.title is not None else existing.title
        content = body.content if body.content is not None else existing.content

        entry = Entry(
            uid=uid,
            date=existing.date,
            reference_date=existing.reference_date,
            title=title,
            type=existing.type,
            content=content,
        )
        try:
            facade.journal.save_entry(entry)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        saved = facade.journal.get_entry(uid)
        if saved is None:
            raise HTTPException(status_code=500, detail="Failed to read back updated entry")
        return _journal_to_wire(saved)
    finally:
        facade.shutdown()


@router.delete("/{uid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_journal(
    uid: str,
    subject: Annotated[str, Depends(current_subject)],
) -> None:
    facade = _facade(subject)
    try:
        if not facade.journal.delete_entry(uid):
            raise HTTPException(status_code=404, detail="Journal entry not found")
    finally:
        facade.shutdown()
