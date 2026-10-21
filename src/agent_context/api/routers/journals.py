"""Journal endpoints: list, read, create, update, delete.

The journal facade stores entries as markdown files. No project or
task integration in this stripped-down router.
"""

from __future__ import annotations

from datetime import date as date_cls
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ...configs import resolve_config_path
from ...core.facade import Facade
from ...journal.facade import Entry, EntryType
from ..auth import current_subject
from ..schemas import (
    JournalAppendIn,
    JournalEntryCreateIn,
    JournalEntryOut,
    JournalEntryUpdateIn,
    JournalListOut,
    JournalSearchOut,
    JournalSearchResultItemOut,
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
                e for e in all_entries if (e.title and needle in e.title.lower()) or needle in e.content.lower()
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


@router.post("/{uid}/append", response_model=JournalEntryOut)
def append_journal(
    uid: str,
    body: JournalAppendIn,
    subject: Annotated[str, Depends(current_subject)],
) -> JournalEntryOut:
    """Append a markdown block to the entry body.

    Atomic write: content is written to a temp file then renamed, so
    concurrent appends are last-writer-safe.

    400 if the entry is memory-synthesis (upsert-only).
    404 if the entry does not exist.
    """
    facade = _facade(subject)
    try:
        entry = facade.journal.append_entry(uid, body.content)
        if entry is None:
            raise HTTPException(status_code=404, detail="Journal entry not found")
        return _journal_to_wire(entry)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        facade.shutdown()


@router.get("/resolve", response_model=JournalEntryOut)
def resolve_journal(
    subject: Annotated[str, Depends(current_subject)],
    type: Annotated[str, Query(alias="type")] = "memory",
    date: Annotated[str, Query()] = "",
) -> JournalEntryOut:
    """Synthesis-aware read for memory type.

    Returns the memory-synthesis entry for the given date if it exists,
    else the memory entry. 404 if neither exists.

    In v1, type must be "memory". Other types return 400.
    """
    if type != "memory":
        raise HTTPException(status_code=400, detail="Only type=memory is supported in v1")
    if not date:
        raise HTTPException(status_code=400, detail="date is required (YYYY-MM-DD)")
    try:
        target_date = date_cls.fromisoformat(date)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {date}") from None

    facade = _facade(subject)
    try:
        entry = facade.journal.resolve_memory_for_date(target_date)
        if entry is None:
            raise HTTPException(
                status_code=404,
                detail=f"No memory entry for {date} (checked memory-synthesis and memory)",
            )
        return _journal_to_wire(entry)
    finally:
        facade.shutdown()


@router.get("/search", response_model=JournalSearchOut)
def search_journals(
    subject: Annotated[str, Depends(current_subject)],
    q: Annotated[str, Query(description="Search query (space-separated tokens)")],
    type: Annotated[str | None, Query(alias="type")] = None,
    from_date: Annotated[str | None, Query(alias="from")] = None,
    to_date: Annotated[str | None, Query(alias="to")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> JournalSearchOut:
    """Full-text search with token scoring.

    Scoring: whole-word match +2, suffix match +1, substring match +1.
    Tokens shorter than 3 chars are ignored.

    Returns results sorted by score desc, then date desc.
    Each result includes a short snippet around the best match.
    """
    entry_type: EntryType | None = None
    if type:
        try:
            entry_type = EntryType(type)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"unknown entry_type: {type}") from None

    date_from: date_cls | None = None
    if from_date:
        try:
            date_from = date_cls.fromisoformat(from_date)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid from date: {from_date}") from None

    date_to: date_cls | None = None
    if to_date:
        try:
            date_to = date_cls.fromisoformat(to_date)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid to date: {to_date}") from None

    facade = _facade(subject)
    try:
        results = facade.journal.search_entries(
            q,
            entry_type=entry_type,
            date_from=date_from,
            date_to=date_to,
            limit=limit,
        )
        items = []
        for entry in results:
            score, pos = facade.journal._score_entry(entry, [t for t in q.split() if len(t) >= 3])
            snippet = facade.journal.get_snippet(entry, pos) if pos >= 0 else ""
            items.append(
                JournalSearchResultItemOut(
                    uid=entry.uid,
                    type=entry.type,
                    date=entry.date,
                    title=entry.title,
                    score=score,
                    snippet=snippet,
                )
            )
        return JournalSearchOut(items=items, total=len(items), query=q)
    finally:
        facade.shutdown()
