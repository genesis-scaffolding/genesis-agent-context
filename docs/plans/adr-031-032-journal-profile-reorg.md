# Plan for adr-031 and adr-032

## Steps

### ADR-031: Profile targets (life_story -> protocol)

1. Update src/agent_context/profile/paths.py:
   - Remove ProfileTarget.LIFE_STORY from enum
   - Add ProfileTarget.PROTOCOL = "protocol"
   - Update TARGET_FILENAME dict: replace life_story -> protocol entry
   - Update TARGETS tuple: (PROFILE, PROTOCOL)
   - Update docstring

2. Update src/agent_context/profile/__init__.py:
   - No changes needed (re-exports from paths)

3. Update src/agent_context/api/schemas.py:
   - Update comment in ProfileWireTarget section (no code change needed)

4. Update src/agent_context/api/routers/profile.py:
   - No code changes needed (uses ProfileTarget values dynamically)

5. Create src/agent_context/ui/pages/protocol.py:
   - Thin wrapper: render() with target=ProfileTarget.PROTOCOL,
     title="Protocol", appropriate caption and empty_hint

6. Update src/agent_context/ui/app.py:
   - Rename nav groups: Persona group gets [Persona], Context group gets [Memory, Protocol]
   - Import ProfileTarget

7. Update README.md:
   - Update architecture section to mention Persona and Protocol targets
   - Update purpose section

### ADR-032: Journal type pruning and new endpoints

8. Update src/agent_context/journal/facade.py:
   a. Prune EntryType enum: remove DAILY, WEEKLY, BRIEFING, MONTHLY, YEARLY,
      PROJECT, MISC, HANDOVER. Add MEMORY_SYNTHESIS, DAILY_HANDOVER.
      Update docstring.
   b. Update _PERIODIC_TYPES to {MEMORY, MEMORY_SYNTHESIS, DAILY_HANDOVER}.
   c. Update _normalize_reference_date: identity branch for all three new types.
      Remove branches for removed types.
   d. In get_entry: catch ValueError from EntryType(type_str) and set type=None.
   e. Add append_entry(uid, block) method: appends markdown block, atomic write.
   f. Add save_entry overwrite logic for MEMORY_SYNTHESIS (upsert: delete old same-day entry).
   g. Add search_entries(query, type_filter, date_from, date_to, limit) method.
   h. Update docstrings.

9. Update src/agent_context/api/schemas.py:
   a. Update JournalWireType comment.
   b. Add JournalAppendIn (content: str).
   c. Add JournalSearchResultItemOut (uid, type, date, title, score: int, snippet: str).
   d. Add JournalSearchOut (items, total, query).

10. Update src/agent_context/api/routers/journals.py:
    a. Add POST /journals/{uid}/append endpoint.
    b. Add GET /journals/resolve endpoint.
    c. Add GET /journals/search endpoint.
    d. Update list endpoint: remove types not in new EntryType enum.

11. Update src/agent_context/ui/pages/journal.py:
    a. Replace _PERIODIC_TYPES with the three new types.
    b. Rename page title to "Memory" and caption.
    c. Remove/create buttons for the old types; add day-pinned navigation
       for memory/memory-synthesis/daily-handover.
    d. Update type filter pills to show only the three new types.

12. Update src/agent_context/ui/app.py:
    a. Rename Journal nav item to Memory.
    b. Update nav group labels (Persona / Context / Account).

13. Update tests/test_profile_unit.py:
    a. Replace all LIFE_STORY / life_story / life-story.md references with
       PROTOCOL / protocol / protocol.md.

14. Update tests/test_profile_api.py:
    a. Replace all life_story references with protocol.
    b. Add tests for protocol target CRUD/snapshots (mirror life_story tests).
    c. Update test_list_returns_both_targets to check for {profile, protocol}.

15. Update tests/test_journal_unit.py:
    a. Remove tests for the old EntryType values (DAILY, WEEKLY, etc.).
    b. Add tests for the three new EntryType values (uniqueness, reference_date).
    c. Add test for unknown type string -> type=None (legacy protection).
    d. Add test for memory-synthesis upsert (second save replaces first).
    e. Add test for append_entry method.
    f. Add test for search_entries scoring.

16. Run make lint, make typecheck, make test and fix any failures.

17. Update README.md architecture notes to remove references to the removed types.
