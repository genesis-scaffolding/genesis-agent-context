"""Facade for journal operations.

Provides access to journal entries stored as markdown files.
Each entry is keyed by a UID (UUID4 hex) and stored as ``{uid}.md``.

Entry types (all day-anchored):
- ``memory`` — raw per-day agent observations.
- ``memory-synthesis`` — synthesised daily memory. Upsert semantics:
  a second save for the same day replaces the existing entry.
- ``daily-handover`` — per-day append log of agent actions after tasks.

All three types are unique per (type, date). A second create for the
same (type, day) is rejected (except memory-synthesis which replaces).

Date semantics:
- ``Entry.date`` is the creation day. Set at creation; not editable via the API.
- ``Entry.reference_date`` is always equal to ``date`` for the three types.
  ``None`` for untyped entries. Server-computed on save.
"""

from __future__ import annotations

import json
import re
import secrets
import string
from dataclasses import dataclass, field
from datetime import date as date_cls
from datetime import datetime
from enum import StrEnum
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from ..tz import to_utc

_ALPHABET = string.ascii_lowercase + string.digits
_TAIL_LENGTH = 6


def new_uid(prefix: str) -> str:
    """Generate a new typed short UID.

    Format: ``{prefix}-{tail}`` where ``tail`` is ``_TAIL_LENGTH`` chars
    from ``_ALPHABET``. Drawn from ``secrets`` for cryptographic strength.
    """
    tail = "".join(secrets.choice(_ALPHABET) for _ in range(_TAIL_LENGTH))
    return f"{prefix}-{tail}"


class EntryType(StrEnum):
    """Journal entry type.

    Exactly three values, all day-anchored. Values are stored verbatim
    in the markdown frontmatter.

    Wire values use hyphens (memory-synthesis, daily-handover) per the
    approved brief naming. Python identifiers use underscores.
    """

    MEMORY = "memory"
    MEMORY_SYNTHESIS = "memory-synthesis"
    DAILY_HANDOVER = "daily-handover"


# Entry types that have a period anchor and therefore participate in
# uniqueness checks. All three are day-anchored.
_PERIODIC_TYPES: frozenset[EntryType] = frozenset(
    {EntryType.MEMORY, EntryType.MEMORY_SYNTHESIS, EntryType.DAILY_HANDOVER}
)


class Entry(BaseModel):
    """A journal entry.

    Attributes:
        uid: UUID4 hex string. Primary identity. Auto-generated if not
            supplied on create.
        date: Creation day. Set at creation; not editable from the API.
        reference_date: Period anchor. For the three day-anchored types,
            this is always ``date``. For untyped entries, ``None``.
            Server-computed on save; not editable from the API.
        title: Optional human title shown in the journal list and detail.
        type: Entry type (memory, memory-synthesis, daily-handover).
            ``None`` for entries with an unrecognized type string on disk.
        content: Markdown body.
        created: When the file was created (from filesystem mtime).
        modified: When the file was last modified (from filesystem mtime).
    """

    uid: str = Field(default_factory=lambda: new_uid("j"))
    date: date_cls
    reference_date: date_cls | None = None
    title: str | None = None
    type: EntryType | None = None
    content: str
    created: datetime | None = None
    modified: datetime | None = None

    model_config = {
        "extra": "ignore",
    }


def _normalize_reference_date(
    entry_type: EntryType | None,
    on: date_cls,
) -> date_cls | None:
    """Return the period anchor for ``entry_type`` applied to ``on``.

    All three current types are day-anchored: reference_date == date.
    """
    if entry_type is None:
        return None
    return on


@dataclass
class RepairReport:
    """Outcome of :meth:`JournalFacade.repair_reference_dates`.

    Attributes:
        repaired: Number of entries whose ``reference-date`` was
            successfully populated.
        failures: ``(uid, error_message)`` pairs for entries that
            could not be repaired (e.g. a duplicate emerged after
            normalising). The migration never raises on per-entry
            failures — they are reported here so the caller can
            decide how to handle them.
    """

    repaired: int = 0
    failures: list[tuple[str, str]] = field(default_factory=list)


_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?", re.DOTALL)
_LEGACY_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _parse(raw: str) -> tuple[dict, str]:
    """Split a file's raw text into frontmatter dict and body.

    Strips a single leading newline from the body so round-trips are
    clean: writing ``"\nbody"`` after the ``---`` separator and
    reading it back yields ``"body"``, not ``"\nbody"``.
    """
    match = _FRONTMATTER_RE.match(raw)
    if not match:
        return {}, raw
    try:
        meta = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError:
        return {}, raw
    if not isinstance(meta, dict):
        return {}, raw
    body = raw[match.end() :]
    if body.startswith("\n"):
        body = body[1:]
    return meta, body


def _serialize(meta: dict, body: str) -> str:
    """Combine frontmatter dict and body into a file's raw text.

    String values that contain YAML-special characters (``:``, ``[``,
    ``&``, etc.) are JSON-quoted so the on-disk round-trip survives
    parsing. The ``date`` value is rendered unquoted as an ISO date
    to match the legacy on-disk format.
    """
    if not meta:
        return body
    lines = ["---"]
    for key, value in meta.items():
        if isinstance(value, date_cls):
            lines.append(f"{key}: {value.isoformat()}")
        elif isinstance(value, str) and _needs_quoting(value):
            lines.append(f"{key}: {json.dumps(value)}")
        else:
            lines.append(f"{key}: {value}")
    lines.append("---")
    lines.append("")
    lines.append(body)
    return "\n".join(lines)


def _needs_quoting(s: str) -> bool:
    """True if a string contains YAML-special characters and would
    not round-trip safely if written unquoted.
    """
    return any(c in s for c in ":#@&*!|>'\"%`[]{},?")


class JournalFacade:
    """Facade for journal entries stored as markdown files.

    Files are named ``{uid}.md``. The directory is created if it does
    not exist.
    """

    def __init__(self, journal_path: str | Path) -> None:
        self._journal_path = Path(journal_path)
        self._journal_path.mkdir(parents=True, exist_ok=True)

    def _entry_path(self, uid: str) -> Path:
        return self._journal_path / f"{uid}.md"

    def get_entry(self, uid: str) -> Entry | None:
        """Return the entry for the given UID, or None if not found.

        Files that fail to parse (malformed frontmatter, missing
        required fields) are silently skipped — the caller sees None
        rather than an exception, so a single bad file does not break
        the list.
        """
        path = self._entry_path(uid)
        if not path.exists():
            return None
        try:
            raw = path.read_text()
            meta, body = _parse(raw)
            stat = path.stat()
            type_str = meta.get("type")
            date_value = meta.get("date")
            # PyYAML parses an unquoted ISO date as a `datetime.date`,
            # not a string. Accept both forms.
            if isinstance(date_value, date_cls):
                entry_date = date_value
            elif isinstance(date_value, str):
                entry_date = date_cls.fromisoformat(date_value)
            else:
                entry_date = date_cls.fromtimestamp(stat.st_ctime)
            if type_str:
                try:
                    entry_type = EntryType(type_str)
                except ValueError:
                    # Unknown type string on disk: treat as None rather than losing the file.
                    entry_type = None
            else:
                entry_type = None
            ref_value = meta.get("reference-date")
            if isinstance(ref_value, date_cls):
                entry_ref = ref_value
            elif isinstance(ref_value, str):
                entry_ref = date_cls.fromisoformat(ref_value)
            else:
                # Legacy file with no ``reference-date`` line.
                # For the three day-anchored types, reference_date
                # defaults to entry_date. Untyped entries default to None.
                entry_ref = entry_date if entry_type in _PERIODIC_TYPES else None
            return Entry(
                uid=uid,
                date=entry_date,
                reference_date=entry_ref,
                title=meta.get("title"),
                type=entry_type,
                content=body,
                created=to_utc(datetime.fromtimestamp(stat.st_ctime)),
                modified=to_utc(datetime.fromtimestamp(stat.st_mtime)),
            )
        except (ValueError, KeyError, OSError, TypeError):
            return None

    def save_entry(self, entry: Entry) -> None:
        """Save an entry by UID.

        Server-side behaviour:

        - Computes the period anchor from ``entry.type`` and ``entry.date``.
          For the three day-anchored types, anchor equals ``date``.
          A mismatch raises ``ValueError``.
        - For day-anchored entries (memory, memory-synthesis, daily-handover),
          rejects the save with ``ValueError`` if another entry of the same
          type already owns the period.
        - Persists ``reference-date`` to the frontmatter whenever it is
          not ``None``.
        - ``memory-synthesis`` entries use upsert semantics: if an entry
          of the same type exists for the same period, the old entry file
          is deleted and the new one takes its place.
        """
        normalized_ref = _normalize_reference_date(entry.type, entry.date)
        if entry.type in _PERIODIC_TYPES:
            assert entry.type is not None  # for type checker
            assert normalized_ref is not None  # periodic types always have an anchor
            if entry.reference_date is not None and entry.reference_date != normalized_ref:
                raise ValueError(
                    f"reference_date {entry.reference_date.isoformat()} does not "
                    f"match the normalised anchor {normalized_ref.isoformat()} "
                    f"for type {entry.type.value}",
                )
            effective_ref = entry.reference_date if entry.reference_date is not None else normalized_ref
            # MEMORY_SYNTHESIS upsert: delete the old entry for the same period if any.
            # This runs BEFORE the uniqueness check so the old entry is gone before
            # we look for duplicates.
            if entry.type == EntryType.MEMORY_SYNTHESIS:
                existing_synth = self.find_for_period(EntryType.MEMORY_SYNTHESIS, entry.date)
                if existing_synth is not None and existing_synth.uid != entry.uid:
                    self.delete_entry(existing_synth.uid)
            if effective_ref is not None:
                existing = self.find_for_period(entry.type, effective_ref)
                if existing is not None and existing.uid != entry.uid:
                    raise ValueError(
                        f"A {entry.type.value} entry for {effective_ref.isoformat()} already exists; edit it instead",
                    )
        else:
            effective_ref = entry.reference_date

        path = self._entry_path(entry.uid)
        meta: dict = {"date": entry.date.isoformat()}
        if effective_ref is not None:
            meta["reference-date"] = effective_ref.isoformat()
        if entry.type is not None:
            meta["type"] = entry.type.value
        if entry.title:
            meta["title"] = entry.title
        path.write_text(_serialize(meta, entry.content))

    def delete_entry(self, uid: str) -> bool:
        """Delete the entry for the given UID. Returns True if removed."""
        path = self._entry_path(uid)
        if not path.exists():
            return False
        path.unlink()
        return True

    def list_entries(self) -> list[Entry]:
        """Return all parseable entries, newest first by file mtime.

        Files that fail to parse (legacy or malformed) are silently
        skipped. Legacy ``YYYY-MM-DD.md`` files from the previous
        filename scheme are also skipped — the user can delete them.
        """
        entries: list[Entry] = []
        for path in sorted(
            self._journal_path.glob("*.md"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        ):
            if _LEGACY_DATE_PATTERN.match(path.stem):
                continue
            entry = self.get_entry(path.stem)
            if entry is not None:
                entries.append(entry)
        return entries

    def find_daily_for_date(self, target_date: date_cls) -> Entry | None:
        """Return the daily entry for ``target_date``, or None if none.

        Thin wrapper around :meth:`find_for_period` kept for callers
        that want a daily-specific name.
        """
        return self.find_for_period(EntryType.MEMORY, target_date)

    def find_for_period(self, entry_type: EntryType, on_or_in: date_cls) -> Entry | None:
        """Return the day-anchored entry for ``entry_type`` on ``on_or_in``.

        For day-anchored types (memory, memory-synthesis, daily-handover),
        ``on_or_in`` is accepted as-is. For untyped entries, always returns None.
        """
        normalized = _normalize_reference_date(entry_type, on_or_in)
        if normalized is None:
            return None
        for entry in self.list_entries():
            if entry.type == entry_type and entry.reference_date == normalized:
                return entry
        return None

    def repair_reference_dates(self) -> RepairReport:
        """One-shot migration for day-anchored entries missing ``reference-date``.

        Walks the journal directory. For each day-anchored entry
        (memory, memory-synthesis, daily-handover) whose on-disk
        ``reference-date`` is missing, computes the period anchor
        (equal to ``date``) and re-saves the file. The re-save
        goes through :meth:`save_entry`, so any duplicate that emerges
        is rejected and reported in ``failures`` rather than raised.

        Idempotent: re-running on already-repaired entries is a no-op.

        Untyped entries are skipped — they have no period anchor.
        """
        report = RepairReport()
        for path in sorted(self._journal_path.glob("*.md")):
            if _LEGACY_DATE_PATTERN.match(path.stem):
                continue
            entry = self.get_entry(path.stem)
            if entry is None:
                continue
            if entry.type not in _PERIODIC_TYPES:
                continue
            if entry.reference_date is not None:
                continue
            entry.reference_date = _normalize_reference_date(entry.type, entry.date)
            try:
                self.save_entry(entry)
                report.repaired += 1
            except ValueError as exc:
                report.failures.append((entry.uid, str(exc)))
        return report

    # ---- Append ---------------------------------------------------------

    def append_entry(self, uid: str, block: str) -> Entry | None:
        """Append a markdown block to the entry body.

        The block is appended after a horizontal-rule separator. Write is
        atomic: content is written to a temp file then renamed over the
        target, so concurrent appends are last-writer-safe.

        Returns the updated entry, or None if the entry does not exist.
        Raises ValueError if the entry is MEMORY_SYNTHESIS (append is not
        meaningful for synthesis content).
        """
        entry = self.get_entry(uid)
        if entry is None:
            return None
        if entry.type == EntryType.MEMORY_SYNTHESIS:
            raise ValueError("Cannot append to a memory-synthesis entry; use create/replace instead")
        separator = "\n\n---\n\n"
        new_content = entry.content + separator + block
        entry.content = new_content
        # Atomic write: write to temp then rename.
        # Build meta dict the same way save_entry does, so frontmatter
        # (reference-date, type, title) is preserved across appends.
        meta: dict = {"date": entry.date.isoformat()}
        if entry.reference_date is not None:
            meta["reference-date"] = entry.reference_date.isoformat()
        if entry.type is not None:
            meta["type"] = entry.type.value
        if entry.title:
            meta["title"] = entry.title
        path = self._entry_path(uid)
        tmp = path.with_suffix(".tmp")
        try:
            tmp.write_text(_serialize(meta, new_content))
            tmp.rename(path)
        except OSError:
            if tmp.exists():
                tmp.unlink()
            raise
        # Re-read to confirm the update.
        return self.get_entry(uid)

    # ---- Search ---------------------------------------------------------

    def search_entries(
        self,
        query: str,
        *,
        entry_type: EntryType | None = None,
        date_from: date_cls | None = None,
        date_to: date_cls | None = None,
        limit: int = 20,
    ) -> list[Entry]:
        """Full-text search with token scoring.

        Scoring per token (best match per entry only):
        - whole-word match: +2
        - suffix match (token is suffix of a word in text): +1
        - substring match: +1 (tokens < 3 chars are ignored)

        Returns entries sorted by score desc, then date desc, capped at limit.
        Only entries with score > 0 are returned.
        """
        tokens = [t.lower() for t in query.split() if len(t) >= 3]
        if not tokens:
            return []
        results: list[tuple[int, date_cls, Entry]] = []
        for entry in self.list_entries():
            if entry_type is not None and entry.type != entry_type:
                continue
            ref = entry.reference_date if entry.reference_date is not None else entry.date
            if date_from is not None and ref < date_from:
                continue
            if date_to is not None and ref > date_to:
                continue
            score, _ = self._score_entry(entry, tokens)
            if score > 0:
                results.append((score, ref, entry))
        # Sort: score desc, date desc
        results.sort(key=lambda x: (-x[0], -x[1].toordinal()))
        return [entry for _, _, entry in results[:limit]]

    def _score_entry(self, entry: Entry, tokens: list[str]) -> tuple[int, int]:
        """Score an entry against token list.

        Returns (total_score, best_match_char_position) for snippet extraction.
        """
        combined = (entry.title or "") + " " + entry.content
        combined_lower = combined.lower()
        words = combined.split()
        total_score = 0
        best_pos = -1
        best_score = 0

        for token in tokens:
            token_best_pos = -1
            token_best_score = 0

            # Whole-word matches: token surrounded by word boundaries. Score +2.
            for m in re.finditer(r"(?<![a-zA-Z])" + re.escape(token) + r"(?![a-zA-Z])", combined_lower):
                token_best_score = 2
                token_best_pos = m.start()
                break  # whole-word match takes priority; no suffix/substring contribution

            # Suffix matches: token matches the end of a word. Score +1.
            if token_best_score == 0:
                for word in words:
                    wl = word.lower()
                    if wl.endswith(token) and wl != token:
                        token_best_score = 1
                        idx = combined_lower.find(wl)
                        if idx != -1:
                            token_best_pos = idx
                        break  # only best match counts

            # Substring matches: token appears anywhere. Score +1.
            if token_best_score == 0:
                m = re.search(re.escape(token), combined_lower)
                if m:
                    token_best_score = 1
                    token_best_pos = m.start()

            if token_best_score > 0:
                total_score += token_best_score
                if token_best_pos != -1 and token_best_score > best_score:
                    best_score = token_best_score
                    best_pos = token_best_pos

        return total_score, best_pos

    def get_snippet(self, entry: Entry, position: int, radius: int = 60) -> str:
        """Extract a snippet of text around ``position``."""
        combined = (entry.title or "") + " " + entry.content
        start = max(0, position - radius)
        end = min(len(combined), position + radius)
        snippet = combined[start:end]
        prefix = "..." if start > 0 else ""
        suffix = "..." if end < len(combined) else ""
        return prefix + snippet + suffix

    # ---- Resolve --------------------------------------------------------

    def resolve_memory_for_date(self, target_date: date_cls) -> Entry | None:
        """Synthesis-aware read for memory type.

        Returns the memory-synthesis entry for that date if it exists,
        else the memory entry, else None.
        """
        synth = self.find_for_period(EntryType.MEMORY_SYNTHESIS, target_date)
        if synth is not None:
            return synth
        return self.find_for_period(EntryType.MEMORY, target_date)
