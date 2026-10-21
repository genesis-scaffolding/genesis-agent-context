# 032. Journal type pruning and new append/resolve/search endpoints

## Context

The journal store has accumulated many entry types (daily, weekly, briefing, monthly,
yearly, project, misc, memory, handover). The brief trims to exactly three, all
day-anchored: memory, memory-synthesis, and daily-handover. The remaining types are
removed from the enum and the uniqueness system.

Additionally, three new API endpoints are required: append (atomic last-writer-safe
append to the body), resolve (synthesis-aware read for memory), and search
(token-scored full-text search across all entries).

## Decision

### EntryType enum: pruning

Remove: DAILY, WEEKLY, BRIEFING, MONTHLY, YEARLY, PROJECT, MISC, HANDOVER.

Add: MEMORY_SYNTHESIS, DAILY_HANDOVER.

New enum values (Python identifier = wire/storage value with underscores for readability):
  MEMORY = memory
  MEMORY_SYNTHESIS = memory-synthesis
  DAILY_HANDOVER = daily-handover

Wire values use hyphens per the brief naming.

### _PERIODIC_TYPES

All three new types are day-anchored. Each pins one entry per (type, date).

  _PERIODIC_TYPES = frozenset({MEMORY, MEMORY_SYNTHESIS, DAILY_HANDOVER})

### _normalize_reference_date

All three new types return on (identity: reference_date == date).

### Unknown types on disk (legacy protection)

A journal entry file whose type frontmatter is not a known EntryType value must
not be lost. On read, treat the unknown type string as type=None. The file remains
visible in list_entries but the type chip is empty.

Implementation: in JournalFacade.get_entry, when EntryType(type_str) raises
ValueError, set entry_type = None and fall through. The raw type string is NOT
preserved; type=None is the sentinel for any unrecognized value.

### memory-synthesis: create-or-replace (upsert) semantics

For MEMORY_SYNTHESIS only, a second create for the same (type, date) is permitted:
it replaces the existing entry (upsert).

Implementation in JournalFacade.save_entry:
1. Find the existing MEMORY_SYNTHESIS entry for the same reference_date.
2. If one exists and its uid differs from the incoming uid, delete the old file.
3. Save with the new uid (no uniqueness check for MEMORY_SYNTHESIS).

### New API: POST /journals/{uid}/append

Appends a markdown block to the entry body. Block is appended after a horizontal
rule separator. Last-writer-safe via atomic write (write temp + rename).

Request body: plain text block (JournalAppendIn with content: str).
Response: updated JournalEntryOut.

Errors:
- 404: entry not found.
- 400: entry type is MEMORY_SYNTHESIS (upsert-only; append not meaningful).

### New API: GET /journals/resolve?type=memory&date=YYYY-MM-DD

Synthesis-aware read. Logic:
1. If memory-synthesis entry exists for that date, return it.
2. Else if memory entry exists for that date, return it.
3. Else 404.

The type param accepts only memory in v1. Other types return 400.
Response: JournalEntryOut.

### New API: GET /journals/search?q=...&type=...&from=...&to=...&limit=...

Full-text search with token scoring:
- whole-word match: +2 per token
- suffix match (token is a suffix of a word): +1 per token
- substring match: +1 per token
- tokens with length < 3 are ignored entirely (no score contribution)

Only the highest-scoring match per entry counts.
Sort: score descending, then date descending.
Limit default: 20.

Snippet: up to 60 chars before and after the best match position,
ellipsized with ... if truncated.

Response shape (JournalSearchOut):
  items: list of {uid, type, date, title, score, snippet}
  total: int
  query: str

### Schema additions

JournalAppendIn: content: str
JournalSearchResultItemOut: uid, type, date, title, score: int, snippet: str
JournalSearchOut: items, total, query

## Status

Accepted

## Consequences

Positive:
- Exactly three types, all day-anchored, clean uniqueness semantics.
- memory-synthesis can be re-run idempotently (key use case for LLM re-synthesis).
- append enables per-entry incremental writes without full-overwrite.
- resolve gives consumers the right entry without knowing the synthesis layer.
- search provides lightweight full-text search with meaningful relevance ranking.

Negative:
- Pruned types (daily, weekly, etc.) are gone. Existing entries on disk with those
  types will have type=None (legacy protection). Files are still readable.
- memory-synthesis upsert deletes the old entry uid on every re-run. No snapshot
  history for synthesis entries (journal does not have the profile snapshot system).
