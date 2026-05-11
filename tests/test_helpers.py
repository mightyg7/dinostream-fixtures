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


from scripts.build_fixtures import normalize_row


def test_normalize_row_combines_date_and_time():
    raw = {
        "game_id": "abc123",
        "date": "2026-05-12",
        "time": "19:00",
        "home_team": "Arsenal",
        "away_team": "Liverpool",
        "venue": "Emirates Stadium",
        "week": "37",
        "league": "ENG-Premier League",
        "season": "2025-2026",
    }
    out = normalize_row(raw, competition="Premier League", competition_group="big5")
    assert out["kickoff_utc"] == datetime(2026, 5, 12, 19, 0, tzinfo=timezone.utc)
    assert out["home"] == "Arsenal"
    assert out["away"] == "Liverpool"
    assert out["competition"] == "Premier League"
    assert out["competition_group"] == "big5"
    assert out["season"] == "2025-2026"
    assert out["matchday"] == "Matchday 37"
    assert out["venue"] == "Emirates Stadium"
    assert out["id"]


def test_normalize_row_missing_time_returns_none_kickoff():
    raw = {
        "game_id": "abc",
        "date": "2026-05-12",
        "time": None,
        "home_team": "A",
        "away_team": "B",
        "league": "ENG-Premier League",
        "season": "2025-2026",
    }
    out = normalize_row(raw, competition="Premier League", competition_group="big5")
    assert out["kickoff_utc"] is None


def test_normalize_row_omits_missing_optional_fields():
    raw = {
        "game_id": "abc",
        "date": "2026-05-12",
        "time": "19:00",
        "home_team": "A",
        "away_team": "B",
        "league": "ENG-Premier League",
        "season": "2025-2026",
    }
    out = normalize_row(raw, competition="Premier League", competition_group="big5")
    assert "venue" not in out
    assert "matchday" not in out


def test_normalize_row_generates_stable_id():
    raw = {
        "game_id": "abc-123",
        "date": "2026-05-12",
        "time": "19:00",
        "home_team": "A",
        "away_team": "B",
        "league": "ENG-Premier League",
        "season": "2025-2026",
    }
    out1 = normalize_row(raw, competition="Premier League", competition_group="big5")
    out2 = normalize_row(raw, competition="Premier League", competition_group="big5")
    assert out1["id"] == out2["id"]
