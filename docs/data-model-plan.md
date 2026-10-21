# GAC Data Model Plan (draft for Gen, 2026-10-09 overnight)

No code changed. This is the decision sheet for t-swz33u (finalise bootstrap).
Grounded in how the **memory system** and the **email-triage handover system**
actually work today — those are the workloads the GAC "journal" store must
support.

## What the two existing systems need

### Memory (agent's per-day journal)

Current design (files on disk, `memory` CLI):

- One raw file per day: `YYYY-MM-DD.md`, append-only bullets with timestamps
- **Compaction**: an overnight `pi -p` agent distils the raw day into
  `YYYY-MM-DD.summary.md` (1–3 dense bullets, conflict-preserving). Readers
  prefer the summary when it exists; the raw file is never modified.
- **Injection**: the assistant extension auto-loads *yesterday's* entry
  (summary if present, else raw) into the system prompt — at most one day.
- **Search**: token-scored full-text search across all date files
  (whole-word > plural/suffix > substring; min token length 3 for substring).
- **Scope**: project (`<cwd>/.pi/memory/`) wins over global
  (`~/.pi/agent/memory/`). Subordinate agents in a project share memory.
- CLI surface: `append`, `read` (range / last-N), `search` (query, from/to,
  limit, scope), `location`, `compaction status` (read-only schedule state).

Data-model requirements this implies:

1. **Append-to-a-period-entry** must be a first-class API op (not
   "overwrite whole entry"). The raw daily file grows all day via appends.
2. **A second file per period** (the synthesis) that readers prefer. In the
   journal model terms: for period P there is at most one *raw* entry and at
   most one *synthesis* entry; reads return the synthesis when present.
3. **Period uniqueness** (the "pin" behaviour already in the journal code):
   exactly one entry per (type, period). The journal facade's
   `reference_date` + save-rejection logic already gives this.
4. **Full-text search** over entries, date-bounded, token-scored.
5. **Scoping** — at minimum per-agent or per-project visibility (project
   wins over global), so subagents share and cross-project stays explicit.

### Handover (email triage + worker ops)

Current design (`handover/inbox/YYYY-MM-DD.md`, `handover/daily/`):

- Append-only **time-ordered log** of everything that came in, written by
  background passes throughout the day (multiple triage passes per day,
  each appends its batch with a timestamp header).
- Line format is convention, not schema: `HH:MM` + `[CATEGORY]` + summary.
  Consumers (the "catch me up" delegation) read the *whole day file, every
  pass* — so append order + timestamps must be preserved and never rewritten.
- **Idempotency by convention**: the triage skill re-reads the day's file to
  know what was already logged (e.g. not duplicating a Genesis task for an
  email already triaged). The file is the agent's own audit trail of
  "what I have already seen today."

Data-model requirements this implies:

1. **Multiple appends per period by multiple writers** (worker passes at
   00:42, 02:44, 08:23... all append to the same daily entry). The API must
   make concurrent appends safe and ordered (or at least last-writer-safe
   with a monotonically appended body).
2. **Read-whole-period** as a cheap op (no pagination gymnastics for a
   day's worth of log lines).
3. The entry is **log-shaped, not doc-shaped** — no section structure, no
   patch semantics needed in practice (patch is fine to keep; the workload
   is append + read-all).

## Proposal for the GAC journal store

Keep the existing journal module (it already has the right primitives:
MD-on-disk, UID + frontmatter, period uniqueness, `reference_date`,
patch/overwrite). On top of it:

### Entry types (prune + purpose)

Drop the productivity-ceremony types (daily, briefing, weekly, monthly,
yearly, project, misc). Keep exactly:

| Type | Purpose | Period | Writers |
|---|---|---|---|
| `memory` | agent's raw per-day observations | day | the agent, all day (append) |
| `memory-synthesis` | overnight compaction of the day | day | compaction agent |
| `handover` | per-day intake log (email triage, worker passes) | day | background workers (append) |
| `note` | freeform agent notes that don't fit a day (optional) | none | the agent |

Rules:

- `memory`, `memory-synthesis`, `handover` are all **day-pinned**: one per
  (user, type, date) — the existing periodic-uniqueness logic, unchanged.
- Readers of `memory` for date D: return `memory-synthesis[D]` if it
  exists, else `memory[D]`. This is a *read convention* (enforce in the CLI /
  a `resolve` API endpoint), not storage magic — both entries coexist on
  disk, raw is never modified by compaction. (Mirrors today exactly.)
- The compaction agent writes `memory-synthesis` via a normal create; if it
  already exists it overwrites (idempotent re-run).

### API additions (beyond the current 6 journal endpoints)

1. `POST /journals/{uid}/append` — append a block to an entry's body
   (ordered, idempotent per client-supplied key optional). **This is the
   missing primitive** for both memory bullets and handover passes.
2. `GET /journals/resolve?type=memory&date=YYYY-MM-DD` — synthesis-aware
   read (returns the effective entry for a period).
3. `GET /journals/search?q=...&type=...&from=...&to=...&limit=...` —
   token-scored full-text search (port the memory CLI's scoring:
   whole-word 2 / suffix 1 / substring 1, skip <3-char substrings).
4. Optional `scope` field on entries + filter on list/search (project /
   global semantics). Defer if it complicates v1 — single-user single-agent
   works without it; the field costs nothing to add to frontmatter now.

### Persona store

- Single target: `persona` (file `persona.md`), versioned snapshots +
  history + restore (existing profile module, minus `life_story`).
- Rationale: life-story is the *user's* story and stays in genesis; the
  agent's identity is one document. (Decision pending Gen's sign-off.)

### UI

- Nav: **Persona / Memory / Handover / Settings**.
- Memory page: day selector + entry view + search box; synthesis badge when
  the effective entry is a synthesis.
- Handover page: day view, raw log, read-only in the UI (workers write).

### CLI surface (for the gac consumer CLI, task t-wcsn5f)

```
gac memory append "<bullet>"            # -> POST /journals/{uid}/append
gac memory read [--last-days N]         # synthesis-aware
gac memory search "<query>" [--from --to --limit]
gac handover read [--date]              # whole-day read
gac persona read|edit|write|history|restore
```

This is a 1:1 mapping of today's `memory` CLI, so the skill + agent habits
transfer unchanged when the pi extension flips the backend from files to GAC.

## Open decisions for Gen (the 4 from yesterday, sharpened)

1. **Entry types**: prune to `memory` / `memory-synthesis` / `handover`
   (+ optional `note`)? (Recommend: yes.)
2. **Persona**: single `persona` target, drop life-story? (Recommend: yes.)
3. **Naming**: keep `journal` as the internal module + API root
   (`/journals`), types carry the meaning — vs rename API to
   `/memory` `/handover`. (Recommend: keep `/journals` — it's accurate,
   the CLI layer is where the friendly names live, and the genesis
   ecosystem already knows the grammar.)
4. **Append endpoint**: confirm as the key new primitive; it's what makes
   both workloads work without whole-entry overwrites.

## Explicitly NOT in this plan

- File-system replication (GAC is the store; files go away for agents once
  the pi extension lands).
- Cross-agent permissions / multi-tenancy beyond a `scope` string.
- Any change to genesis-productivity (its journal stays as-is for the user's
  own ceremonies).
