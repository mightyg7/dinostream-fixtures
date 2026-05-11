from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

from scripts.build_fixtures import fetch_competition, BIG5_LEAGUE_MAP, build_bundle


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


def test_build_bundle_combines_sources(monkeypatch, sample_df, now):
    def fake_read_schedule(self):
        return sample_df

    monkeypatch.setattr("soccerdata.FBref.read_schedule", fake_read_schedule)

    bundle = build_bundle(now=now, window_days=14)

    assert bundle["window_days"] == 14
    assert bundle["generated_at"].endswith("Z")
    assert len(bundle["fixtures"]) >= 2  # at least Big-5 in-window rows
    groups = {f["competition_group"] for f in bundle["fixtures"]}
    assert groups.issubset({"big5", "cup", "international"})


def test_build_bundle_continues_when_a_source_fails(monkeypatch, sample_df, now):
    call_count = {"n": 0}

    def fake_read_schedule(self):
        call_count["n"] += 1
        if call_count["n"] == 2:
            raise RuntimeError("scraper down")
        return sample_df

    monkeypatch.setattr("soccerdata.FBref.read_schedule", fake_read_schedule)

    bundle = build_bundle(now=now, window_days=14)
    assert len(bundle["fixtures"]) >= 1  # bundle still emitted


def test_build_bundle_sorts_by_kickoff(monkeypatch, sample_df, now):
    monkeypatch.setattr("soccerdata.FBref.read_schedule", lambda self: sample_df)
    bundle = build_bundle(now=now, window_days=14)
    kickoffs = [f["kickoff_utc"] for f in bundle["fixtures"]]
    assert kickoffs == sorted(kickoffs)


def test_cli_writes_validated_json(tmp_path, monkeypatch, sample_df):
    import json
    import jsonschema

    monkeypatch.setattr("soccerdata.FBref.read_schedule", lambda self: sample_df)
    out = tmp_path / "fixtures.json"

    from scripts.build_fixtures import run_cli

    rc = run_cli(["--out", str(out), "--window-days", "14"])
    assert rc == 0
    data = json.loads(out.read_text())

    schema = json.loads(
        (Path(__file__).parent.parent / "schema" / "fixtures.schema.json").read_text()
    )
    jsonschema.validate(data, schema)

    assert data["window_days"] == 14
    assert "generated_at" in data
    assert len(data["fixtures"]) >= 1
