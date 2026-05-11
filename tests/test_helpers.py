from datetime import datetime, timezone

from scripts.build_fixtures import current_season


def test_current_season_august_starts_new_season():
    now = datetime(2025, 8, 1, tzinfo=timezone.utc)
    assert current_season(now) == "2025-2026"


def test_current_season_january_stays_in_started_season():
    now = datetime(2026, 1, 15, tzinfo=timezone.utc)
    assert current_season(now) == "2025-2026"


def test_current_season_july_uses_previous_season():
    now = datetime(2025, 7, 5, tzinfo=timezone.utc)
    assert current_season(now) == "2024-2025"


from scripts.build_fixtures import filter_window


def _row(kickoff, **extra):
    base = {"kickoff_utc": kickoff, "home": "A", "away": "B"}
    base.update(extra)
    return base


def test_filter_window_excludes_past():
    now = datetime(2026, 5, 11, 12, 0, tzinfo=timezone.utc)
    rows = [_row(datetime(2026, 5, 10, 12, 0, tzinfo=timezone.utc))]
    assert filter_window(rows, now, window_days=14) == []


def test_filter_window_includes_within_14_days():
    now = datetime(2026, 5, 11, 12, 0, tzinfo=timezone.utc)
    rows = [
        _row(datetime(2026, 5, 12, 19, 0, tzinfo=timezone.utc)),
        _row(datetime(2026, 5, 24, 19, 0, tzinfo=timezone.utc)),
    ]
    assert len(filter_window(rows, now, window_days=14)) == 2


def test_filter_window_excludes_beyond_14_days():
    now = datetime(2026, 5, 11, 12, 0, tzinfo=timezone.utc)
    rows = [_row(datetime(2026, 6, 1, 19, 0, tzinfo=timezone.utc))]
    assert filter_window(rows, now, window_days=14) == []


def test_filter_window_drops_rows_with_no_kickoff():
    now = datetime(2026, 5, 11, 12, 0, tzinfo=timezone.utc)
    rows = [_row(None)]
    assert filter_window(rows, now, window_days=14) == []


