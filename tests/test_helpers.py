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
