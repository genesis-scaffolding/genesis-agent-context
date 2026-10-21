"""Unit tests for the journal facade (new model: memory, memory-synthesis, daily-handover)."""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import pytest

from agent_context.journal.facade import Entry, EntryType, JournalFacade


class TestParseFrontmatter:
    """Tests for the frontmatter parser."""

    def test_no_frontmatter_returns_empty_meta_and_full_body(self) -> None:
        from agent_context.journal.facade import _parse

        meta, body = _parse("Hello world\n")
        assert meta == {}
        assert body == "Hello world\n"

    def test_full_frontmatter_parses(self) -> None:
        from datetime import date as date_cls

        from agent_context.journal.facade import _parse

        raw = "---\ndate: 2026-09-05\ntype: memory\ntitle: Hi\n---\n\nBody text\n"
        meta, body = _parse(raw)
        # PyYAML parses unquoted ISO dates as datetime.date objects.
        assert meta == {"date": date_cls(2026, 9, 5), "type": "memory", "title": "Hi"}
        assert body == "Body text\n"

    def test_malformed_frontmatter_falls_back_to_body(self) -> None:
        from agent_context.journal.facade import _parse

        raw = "---\ntype: memory\nbody without closing fence"
        meta, body = _parse(raw)
        assert meta == {}
        assert body == raw


class TestSerialize:
    """Tests for the frontmatter serializer."""

    def test_empty_meta_writes_body_only(self) -> None:
        from agent_context.journal.facade import _serialize

        assert _serialize({}, "body text\n") == "body text\n"

    def test_meta_writes_frontmatter_block(self) -> None:
        from agent_context.journal.facade import _serialize

        out = _serialize({"date": "2026-09-05", "type": "memory", "title": "Hi"}, "body\n")
        assert out.startswith("---\n")
        assert "date: 2026-09-05" in out
        assert "type: memory" in out
        assert "title: Hi" in out
        assert out.endswith("\nbody\n")


class TestJournalFacade:
    """End-to-end tests against a temporary journal directory."""

    def test_save_then_load_round_trips_full_entry(self, tmp_path: Path) -> None:
        facade = JournalFacade(tmp_path)
        entry = Entry(
            date=date(2026, 9, 5),
            title="Day notes",
            type=EntryType.MEMORY,
            content="Leg press 5x5\n",
        )
        facade.save_entry(entry)

        loaded = facade.get_entry(entry.uid)
        assert loaded is not None
        assert loaded.uid == entry.uid
        assert loaded.title == "Day notes"
        assert loaded.type == EntryType.MEMORY
        assert loaded.content == "Leg press 5x5\n"
        assert loaded.date == date(2026, 9, 5)

    def test_uid_is_generated_on_save(self, tmp_path: Path) -> None:
        facade = JournalFacade(tmp_path)
        entry = Entry(date=date(2026, 9, 5), content="x")
        assert entry.uid  # factory ran on construction
        assert re.match(r"^j-[0-9a-z]{6}$", entry.uid)
        facade.save_entry(entry)
        loaded = facade.get_entry(entry.uid)
        assert loaded is not None
        assert loaded.uid == entry.uid

    def test_save_with_no_type_or_title_writes_minimal_frontmatter(self, tmp_path: Path) -> None:
        facade = JournalFacade(tmp_path)
        entry = Entry(date=date(2026, 9, 5), content="Just a body\n")
        facade.save_entry(entry)

        raw = (tmp_path / f"{entry.uid}.md").read_text()
        assert raw.startswith("---\n")
        assert "date: 2026-09-05" in raw
        # No `type:` or `title:` lines
        assert "type:" not in raw
        assert "title:" not in raw
        assert raw.endswith("\nJust a body\n")

        loaded = facade.get_entry(entry.uid)
        assert loaded is not None
        assert loaded.title is None
        assert loaded.type is None
        assert loaded.content == "Just a body\n"

    def test_list_entries_returns_newest_first(self, tmp_path: Path) -> None:
        facade = JournalFacade(tmp_path)
        for d in [date(2026, 9, 1), date(2026, 9, 5), date(2026, 9, 3)]:
            entry = Entry(date=d, content=f"body for {d}\n")
            facade.save_entry(entry)
        listed = facade.list_entries()
        # Newest first by file mtime.
        assert [e.date for e in listed] == [
            date(2026, 9, 3),
            date(2026, 9, 5),
            date(2026, 9, 1),
        ]

    def test_unknown_type_string_results_in_type_none(self, tmp_path: Path) -> None:
        # An unrecognized type string on disk is not lost: the file is
        # readable but type=None. This protects legacy entries.
        facade = JournalFacade(tmp_path)
        # Write a file with a bogus type directly.
        path = tmp_path / "j-legacy00.md"
        path.write_text("---\ndate: 2026-09-05\ntype: garbled\n---\n\nbody\n")
        loaded = facade.get_entry("j-legacy00")
        assert loaded is not None
        assert loaded.type is None  # unknown type -> None, not skip
        assert loaded.content == "body\n"

    def test_memory_uniqueness_blocks_second_save(self, tmp_path: Path) -> None:
        facade = JournalFacade(tmp_path)
        a = Entry(date=date(2026, 9, 5), type=EntryType.MEMORY, content="a")
        facade.save_entry(a)

        b = Entry(date=date(2026, 9, 5), type=EntryType.MEMORY, content="b")
        with pytest.raises(ValueError, match="memory entry for 2026-09-05"):
            facade.save_entry(b)

        # Edit of the same entry (same uid) is fine
        a.content = "a edited"
        facade.save_entry(a)
        loaded = facade.get_entry(a.uid)
        assert loaded is not None
        assert loaded.content == "a edited"

    def test_different_dates_can_have_different_memory_entries(self, tmp_path: Path) -> None:
        facade = JournalFacade(tmp_path)
        a = Entry(date=date(2026, 9, 5), type=EntryType.MEMORY, content="a")
        b = Entry(date=date(2026, 9, 6), type=EntryType.MEMORY, content="b")
        facade.save_entry(a)
        facade.save_entry(b)  # different date, no collision
        assert len(facade.list_entries()) == 2

    def test_memory_synthesis_upsert_replaces_same_day(self, tmp_path: Path) -> None:
        # memory-synthesis is the one type that allows re-creation for the
        # same day: the second save replaces the first.
        facade = JournalFacade(tmp_path)
        a = Entry(date=date(2026, 9, 5), type=EntryType.MEMORY_SYNTHESIS, content="first synthesis")
        facade.save_entry(a)
        uid_a = a.uid

        b = Entry(date=date(2026, 9, 5), type=EntryType.MEMORY_SYNTHESIS, content="second synthesis")
        facade.save_entry(b)

        # Old entry is gone (replaced).
        assert facade.get_entry(uid_a) is None
        # New entry is there.
        loaded = facade.get_entry(b.uid)
        assert loaded is not None
        assert loaded.content == "second synthesis"
        assert len(facade.list_entries()) == 1

    def test_memory_synthesis_different_days_both_succeed(self, tmp_path: Path) -> None:
        facade = JournalFacade(tmp_path)
        a = Entry(date=date(2026, 9, 5), type=EntryType.MEMORY_SYNTHESIS, content="a")
        b = Entry(date=date(2026, 9, 6), type=EntryType.MEMORY_SYNTHESIS, content="b")
        facade.save_entry(a)
        facade.save_entry(b)
        assert len(facade.list_entries()) == 2

    def test_daily_handover_uniqueness_blocks_second_save(self, tmp_path: Path) -> None:
        facade = JournalFacade(tmp_path)
        a = Entry(date=date(2026, 9, 5), type=EntryType.DAILY_HANDOVER, content="a")
        facade.save_entry(a)
        b = Entry(date=date(2026, 9, 5), type=EntryType.DAILY_HANDOVER, content="b")
        with pytest.raises(ValueError, match="daily-handover entry for 2026-09-05"):
            facade.save_entry(b)

    def test_find_daily_for_date(self, tmp_path: Path) -> None:
        # find_daily_for_date is now a thin wrapper around find_for_period(MEMORY, ...).
        # We test it with memory entries.
        facade = JournalFacade(tmp_path)
        a = Entry(date=date(2026, 9, 5), type=EntryType.MEMORY, content="a")
        b = Entry(date=date(2026, 9, 6), type=EntryType.MEMORY, content="b")
        facade.save_entry(a)
        facade.save_entry(b)

        hit = facade.find_daily_for_date(date(2026, 9, 5))
        assert hit is not None
        assert hit.uid == a.uid

        assert facade.find_daily_for_date(date(2026, 9, 7)) is None

    def test_delete_entry_by_uid(self, tmp_path: Path) -> None:
        facade = JournalFacade(tmp_path)
        entry = Entry(date=date(2026, 9, 5), content="x")
        facade.save_entry(entry)
        assert facade.delete_entry(entry.uid) is True
        assert facade.get_entry(entry.uid) is None
        assert facade.delete_entry(entry.uid) is False

    def test_legacy_date_filename_is_skipped(self, tmp_path: Path) -> None:
        (tmp_path / "2026-09-06.md").write_text("Old body text\n")
        facade = JournalFacade(tmp_path)
        assert facade.list_entries() == []
        assert (tmp_path / "2026-09-06.md").exists()


class TestReferenceDate:
    """Server-side period anchoring: all three types use identity (ref == date)."""

    def test_memory_save_stores_reference_date_equal_to_date(self, tmp_path: Path) -> None:
        facade = JournalFacade(tmp_path)
        entry = Entry(date=date(2026, 9, 5), type=EntryType.MEMORY, content="x")
        facade.save_entry(entry)
        loaded = facade.get_entry(entry.uid)
        assert loaded is not None
        assert loaded.reference_date == date(2026, 9, 5)

    def test_memory_synthesis_save_stores_reference_date_equal_to_date(self, tmp_path: Path) -> None:
        facade = JournalFacade(tmp_path)
        entry = Entry(date=date(2026, 9, 5), type=EntryType.MEMORY_SYNTHESIS, content="x")
        facade.save_entry(entry)
        loaded = facade.get_entry(entry.uid)
        assert loaded is not None
        assert loaded.reference_date == date(2026, 9, 5)

    def test_daily_handover_save_stores_reference_date_equal_to_date(self, tmp_path: Path) -> None:
        facade = JournalFacade(tmp_path)
        entry = Entry(date=date(2026, 9, 15), type=EntryType.DAILY_HANDOVER, content="x")
        facade.save_entry(entry)
        loaded = facade.get_entry(entry.uid)
        assert loaded is not None
        assert loaded.reference_date == date(2026, 9, 15)

    def test_untyped_entry_saves_omit_reference_date(self, tmp_path: Path) -> None:
        facade = JournalFacade(tmp_path)
        entry = Entry(date=date(2026, 9, 5), content="x")  # no type
        facade.save_entry(entry)
        loaded = facade.get_entry(entry.uid)
        assert loaded is not None
        assert loaded.reference_date is None

    def test_find_for_period_memory(self, tmp_path: Path) -> None:
        facade = JournalFacade(tmp_path)
        m = Entry(date=date(2026, 9, 5), type=EntryType.MEMORY, content="m")
        facade.save_entry(m)
        hit = facade.find_for_period(EntryType.MEMORY, date(2026, 9, 5))
        assert hit is not None and hit.uid == m.uid
        assert facade.find_for_period(EntryType.MEMORY, date(2026, 9, 6)) is None

    def test_find_for_period_memory_synthesis(self, tmp_path: Path) -> None:
        facade = JournalFacade(tmp_path)
        s = Entry(date=date(2026, 9, 5), type=EntryType.MEMORY_SYNTHESIS, content="s")
        facade.save_entry(s)
        hit = facade.find_for_period(EntryType.MEMORY_SYNTHESIS, date(2026, 9, 5))
        assert hit is not None and hit.uid == s.uid
        assert facade.find_for_period(EntryType.MEMORY_SYNTHESIS, date(2026, 9, 6)) is None

    def test_find_for_period_daily_handover(self, tmp_path: Path) -> None:
        facade = JournalFacade(tmp_path)
        h = Entry(date=date(2026, 9, 5), type=EntryType.DAILY_HANDOVER, content="h")
        facade.save_entry(h)
        hit = facade.find_for_period(EntryType.DAILY_HANDOVER, date(2026, 9, 5))
        assert hit is not None and hit.uid == h.uid
        assert facade.find_for_period(EntryType.DAILY_HANDOVER, date(2026, 9, 6)) is None

    def test_legacy_daily_defaults_reference_date_to_date(self, tmp_path: Path) -> None:
        # A file written before this ADR has no ``reference-date`` line.
        # For entries with no type, reference_date defaults to None.
        path = tmp_path / "j-legacy01.md"
        path.write_text("---\ndate: 2026-09-05\ntype: memory\n---\n\nbody\n")
        facade = JournalFacade(tmp_path)
        loaded = facade.get_entry("j-legacy01")
        assert loaded is not None
        assert loaded.reference_date == date(2026, 9, 5)


class TestAppend:
    """Tests for append_entry."""

    def test_append_adds_block_after_separator(self, tmp_path: Path) -> None:
        facade = JournalFacade(tmp_path)
        entry = Entry(date=date(2026, 9, 5), type=EntryType.MEMORY, content="First block")
        facade.save_entry(entry)

        updated = facade.append_entry(entry.uid, "Second block")
        assert updated is not None
        assert "First block" in updated.content
        assert "Second block" in updated.content
        assert "\n\n---\n\n" in updated.content

    def test_append_returns_none_for_missing_entry(self, tmp_path: Path) -> None:
        facade = JournalFacade(tmp_path)
        result = facade.append_entry("nonexistent", "block")
        assert result is None

    def test_append_rejects_memory_synthesis(self, tmp_path: Path) -> None:
        facade = JournalFacade(tmp_path)
        entry = Entry(date=date(2026, 9, 5), type=EntryType.MEMORY_SYNTHESIS, content="x")
        facade.save_entry(entry)
        with pytest.raises(ValueError, match="memory-synthesis"):
            facade.append_entry(entry.uid, "extra content")

    def test_append_preserves_type_and_reference_date(self, tmp_path: Path) -> None:
        # Regression: append_entry must not clobber frontmatter fields.
        # After append, the returned entry and the re-read entry must
        # still have the correct type, reference_date, and title; and
        # the day-pinning uniqueness check must still reject a second
        # create for the same (type, day).
        facade = JournalFacade(tmp_path)
        entry = Entry(
            date=date(2026, 9, 5),
            type=EntryType.MEMORY,
            title="Day notes",
            content="First block",
        )
        facade.save_entry(entry)

        # Append a block.
        updated = facade.append_entry(entry.uid, "Second block")
        assert updated is not None
        assert updated.type == EntryType.MEMORY
        assert updated.reference_date == date(2026, 9, 5)
        assert updated.title == "Day notes"
        assert "Second block" in updated.content

        # Re-read from disk.
        reloaded = facade.get_entry(entry.uid)
        assert reloaded is not None
        assert reloaded.type == EntryType.MEMORY
        assert reloaded.reference_date == date(2026, 9, 5)
        assert reloaded.title == "Day notes"

        # Day-pinning uniqueness is still enforced.
        duplicate = Entry(date=date(2026, 9, 5), type=EntryType.MEMORY, content="another")
        with pytest.raises(ValueError, match="memory entry for 2026-09-05"):
            facade.save_entry(duplicate)


class TestResolve:
    """Tests for resolve_memory_for_date."""

    def test_resolve_returns_synthesis_when_present(self, tmp_path: Path) -> None:
        facade = JournalFacade(tmp_path)
        synth = Entry(date=date(2026, 9, 5), type=EntryType.MEMORY_SYNTHESIS, content="synth")
        raw = Entry(date=date(2026, 9, 5), type=EntryType.MEMORY, content="raw")
        facade.save_entry(synth)
        facade.save_entry(raw)

        hit = facade.resolve_memory_for_date(date(2026, 9, 5))
        assert hit is not None
        assert hit.uid == synth.uid
        assert hit.content == "synth"

    def test_resolve_returns_raw_when_no_synthesis(self, tmp_path: Path) -> None:
        facade = JournalFacade(tmp_path)
        raw = Entry(date=date(2026, 9, 5), type=EntryType.MEMORY, content="raw")
        facade.save_entry(raw)

        hit = facade.resolve_memory_for_date(date(2026, 9, 5))
        assert hit is not None
        assert hit.uid == raw.uid

    def test_resolve_returns_none_when_nothing_exists(self, tmp_path: Path) -> None:
        facade = JournalFacade(tmp_path)
        hit = facade.resolve_memory_for_date(date(2026, 9, 5))
        assert hit is None


class TestSearch:
    """Tests for search_entries and get_snippet."""

    def test_search_whole_word_match_scores_2(self, tmp_path: Path) -> None:
        facade = JournalFacade(tmp_path)
        entry = Entry(date=date(2026, 9, 5), type=EntryType.MEMORY, title="test", content="hello world")
        facade.save_entry(entry)
        results = facade.search_entries("hello")
        assert len(results) == 1
        score, _ = facade._score_entry(entry, ["hello"])
        assert score == 2

    def test_search_suffix_match_scores_1(self, tmp_path: Path) -> None:
        facade = JournalFacade(tmp_path)
        entry = Entry(date=date(2026, 9, 5), type=EntryType.MEMORY, content="testing something")
        facade.save_entry(entry)
        results = facade.search_entries("ing")
        assert len(results) == 1
        score, _ = facade._score_entry(entry, ["ing"])
        assert score == 1

    def test_search_substring_match_scores_1(self, tmp_path: Path) -> None:
        facade = JournalFacade(tmp_path)
        entry = Entry(date=date(2026, 9, 5), type=EntryType.MEMORY, content="hello world")
        facade.save_entry(entry)
        # "llo" is a substring but not a whole word or suffix of any word starting with "llo"
        results = facade.search_entries("llo")
        assert len(results) == 1
        score, _ = facade._score_entry(entry, ["llo"])
        assert score == 1

    def test_search_short_token_ignored(self, tmp_path: Path) -> None:
        facade = JournalFacade(tmp_path)
        entry = Entry(date=date(2026, 9, 5), type=EntryType.MEMORY, content="hello world")
        facade.save_entry(entry)
        results = facade.search_entries("he")
        assert len(results) == 0

    def test_search_filters_by_type(self, tmp_path: Path) -> None:
        facade = JournalFacade(tmp_path)
        e1 = Entry(date=date(2026, 9, 5), type=EntryType.MEMORY, content="hello")
        e2 = Entry(date=date(2026, 9, 5), type=EntryType.DAILY_HANDOVER, content="hello")
        facade.save_entry(e1)
        facade.save_entry(e2)
        results = facade.search_entries("hello", entry_type=EntryType.MEMORY)
        assert len(results) == 1
        assert results[0].uid == e1.uid

    def test_search_filters_by_date_range(self, tmp_path: Path) -> None:
        facade = JournalFacade(tmp_path)
        e1 = Entry(date=date(2026, 9, 5), type=EntryType.MEMORY, content="target")
        e2 = Entry(date=date(2026, 9, 10), type=EntryType.MEMORY, content="target")
        facade.save_entry(e1)
        facade.save_entry(e2)
        results = facade.search_entries("target", date_from=date(2026, 9, 6), date_to=date(2026, 9, 12))
        assert len(results) == 1
        assert results[0].uid == e2.uid

    def test_search_sorts_by_score_then_date(self, tmp_path: Path) -> None:
        facade = JournalFacade(tmp_path)
        # Two matches with different scores.
        e1 = Entry(date=date(2026, 9, 5), type=EntryType.MEMORY, content="hello world")  # score=2
        e2 = Entry(date=date(2026, 9, 6), type=EntryType.MEMORY, content="hello")  # score=2
        e3 = Entry(date=date(2026, 9, 7), type=EntryType.MEMORY, content="hello world")  # score=2
        facade.save_entry(e1)
        facade.save_entry(e2)
        facade.save_entry(e3)
        results = facade.search_entries("hello")
        # All have score=2; sorted by date desc: 7, 6, 5
        assert [e.date for e in results] == [date(2026, 9, 7), date(2026, 9, 6), date(2026, 9, 5)]

    def test_search_respects_limit(self, tmp_path: Path) -> None:
        facade = JournalFacade(tmp_path)
        for d in [date(2026, 9, i) for i in range(1, 11)]:
            entry = Entry(date=d, type=EntryType.MEMORY, content="hello world")
            facade.save_entry(entry)
        results = facade.search_entries("hello", limit=3)
        assert len(results) == 3

    def test_search_empty_query_returns_empty(self, tmp_path: Path) -> None:
        facade = JournalFacade(tmp_path)
        entry = Entry(date=date(2026, 9, 5), type=EntryType.MEMORY, content="hello")
        facade.save_entry(entry)
        results = facade.search_entries("")
        assert results == []

    def test_get_snippet_returns_surrounding_context(self, tmp_path: Path) -> None:
        facade = JournalFacade(tmp_path)
        entry = Entry(date=date(2026, 9, 5), type=EntryType.MEMORY, content="prefix hello suffix")
        snippet = facade.get_snippet(entry, position=8)  # "hello" starts at position 8
        assert "hello" in snippet


class TestRepair:
    """Tests for repair_reference_dates."""

    def test_repair_reference_dates_is_idempotent(self, tmp_path: Path) -> None:
        (tmp_path / "j-legacy01.md").write_text("---\ndate: 2026-09-05\ntype: memory\n---\n\nbody\n")
        facade = JournalFacade(tmp_path)
        first = facade.repair_reference_dates()
        second = facade.repair_reference_dates()
        assert first.repaired == 0  # memory already has ref=date
        assert second.repaired == 0
