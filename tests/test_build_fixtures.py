from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

from scripts.build_fixtures import fetch_competition, BIG5_LEAGUE_MAP


SAMPLE_CSV = Path(__file__).parent / "data" / "sample_schedule.csv"


@pytest.fixture
def now():
    return datetime(2026, 5, 11, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def sample_df():
    return pd.read_csv(SAMPLE_CSV)


def test_fetch_competition_filters_and_normalizes(monkeypatch, sample_df, now):
    captured = {}

    def fake_read_schedule(self):
        captured["leagues"] = self.leagues
        captured["seasons"] = self.seasons
        return sample_df

    monkeypatch.setattr("soccerdata.FBref.read_schedule", fake_read_schedule)

    rows = fetch_competition(
        source="fbref",
        leagues=list(BIG5_LEAGUE_MAP.keys()),
        season="2025-2026",
        now=now,
        window_days=14,
        league_to_competition=BIG5_LEAGUE_MAP,
        competition_group="big5",
    )

    assert {r["home"] for r in rows} == {"Arsenal", "Real Madrid"}
    assert all(r["competition_group"] == "big5" for r in rows)
    # soccerdata normalises "2025-2026" → "2526" internally
    assert captured["seasons"] == ["2526"]
