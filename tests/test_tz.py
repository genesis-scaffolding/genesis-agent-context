"""Tests for ``agent_context.tz``: tz-aware UTC convention."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

from agent_context.tz import format_local, to_local, to_utc, to_utc_optional


class TestToUtc:
    """``to_utc`` coerces naive and aware datetimes to tz-aware UTC."""

    def test_naive_assumed_local_and_converted(self) -> None:
        # Build a naive local datetime matching the system clock, then
        # round-trip through to_utc should land on the same instant.
        local_now = datetime.now()
        utc = to_utc(local_now)
        assert utc.tzinfo is UTC
        # Convert back to local (naive) and compare instants.
        local_back = utc.astimezone().replace(tzinfo=None)
        assert abs((local_back - local_now).total_seconds()) < 1

    def test_aware_non_utc_converted(self) -> None:
        # Tokyo time: +09:00, no DST.
        tokyo = timezone(timedelta(hours=9))
        dt = datetime(2026, 9, 7, 14, 0, tzinfo=tokyo)
        utc = to_utc(dt)
        assert utc.tzinfo is UTC
        assert utc.hour == 5  # 14:00 JST -> 05:00 UTC

    def test_aware_utc_passes_through(self) -> None:
        dt = datetime(2026, 9, 7, 5, 0, tzinfo=UTC)
        utc = to_utc(dt)
        assert utc is dt or utc == dt
        assert utc.tzinfo is UTC

    def test_negative_offset(self) -> None:
        # New York EDT: -04:00 in September.
        ny = timezone(timedelta(hours=-4))
        dt = datetime(2026, 9, 7, 10, 0, tzinfo=ny)
        utc = to_utc(dt)
        assert utc.tzinfo is UTC
        assert utc.hour == 14  # 10:00 EDT -> 14:00 UTC


class TestToLocal:
    """``to_local`` converts UTC to system local for display."""

    def test_aware_utc_to_local(self) -> None:
        utc = datetime(2026, 9, 7, 14, 0, tzinfo=UTC)
        local = to_local(utc)
        # The local representation equals the local clock face of the UTC
        # instant; for a non-UTC zone, the hour must differ from 14.
        local_tz = datetime.now(UTC).astimezone().tzinfo
        assert local_tz is not None
        if local_tz.utcoffset(utc) != timedelta(0):
            assert local.hour != 14 or local.day != utc.day
        # Round trip: to_local -> to_utc -> original UTC.
        assert to_utc(local) == utc

    def test_naive_passes_through(self) -> None:
        dt = datetime(2026, 9, 7, 14, 0)
        assert to_local(dt) is dt


class TestToUtcOptional:
    """``to_utc_optional`` handles None."""

    def test_none(self) -> None:
        assert to_utc_optional(None) is None

    def test_value(self) -> None:
        result = to_utc_optional(datetime(2026, 9, 7, 14, 0))
        assert result is not None
        assert result.tzinfo is UTC


class TestFormatLocal:
    """``format_local`` formats UTC as a local-time string."""

    def test_none_returns_empty(self) -> None:
        assert format_local(None) == ""

    def test_default_format(self) -> None:
        utc = datetime(2026, 9, 7, 14, 30, tzinfo=UTC)
        formatted = format_local(utc)
        # Should match YYYY-MM-DD HH:MM after local conversion.
        assert len(formatted) == 16
        assert formatted[4] == "-"
        assert formatted[7] == "-"
        assert formatted[10] == " "
        assert formatted[13] == ":"

    def test_custom_format(self) -> None:
        utc = datetime(2026, 9, 7, 14, 30, tzinfo=UTC)
        assert format_local(utc, "%Y") == str(datetime.now().year)
