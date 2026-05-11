import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import jsonschema
import pytest

from scripts.build_fixtures import build_bundle, fetch_matches, run_cli, _normalize_match


@pytest.fixture
def now():
    return datetime(2026, 5, 11, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def sample_response():
    """Mimic football-data.org /v4/matches payload shape."""
    return {
        "matches": [
            {
                "id": 100,
                "utcDate": "2026-05-12T19:00:00Z",
                "status": "SCHEDULED",
                "matchday": 37,
                "competition": {"code": "PL", "name": "Premier League"},
                "season": {"startDate": "2025-08-15", "endDate": "2026-05-24"},
                "homeTeam": {"name": "Arsenal FC", "shortName": "Arsenal"},
                "awayTeam": {"name": "Liverpool FC", "shortName": "Liverpool"},
            },
            {
                "id": 101,
                "utcDate": "2026-05-15T15:00:00Z",
                "status": "SCHEDULED",
                "matchday": 38,
                "competition": {"code": "PD", "name": "La Liga"},
                "season": {"startDate": "2025-08-15", "endDate": "2026-05-24"},
                "homeTeam": {"name": "Real Madrid", "shortName": "Real Madrid"},
                "awayTeam": {"name": "FC Barcelona", "shortName": "Barcelona"},
            },
            {
                "id": 102,
                "utcDate": "2026-05-10T19:00:00Z",
                "status": "SCHEDULED",
                "matchday": 6,
                "competition": {"code": "CL", "name": "UEFA Champions League"},
                "season": {"startDate": "2025-09-01", "endDate": "2026-06-01"},
                "homeTeam": {"name": "Manchester City", "shortName": "Man City"},
                "awayTeam": {"name": "Bayern Munchen", "shortName": "Bayern"},
            },
            {
                "id": 103,
                "utcDate": "2026-06-15T19:00:00Z",
                "status": "SCHEDULED",
                "competition": {"code": "PL", "name": "Premier League"},
                "season": {"startDate": "2026-08-15", "endDate": "2027-05-24"},
                "homeTeam": {"name": "Chelsea", "shortName": "Chelsea"},
                "awayTeam": {"name": "Tottenham", "shortName": "Spurs"},
            },
        ]
    }


def _stub_get(sample_response):
    """Dispatch per-competition: each call returns only the matches whose code is in the URL.

    The current build_fixtures hits `/v4/competitions/{CODE}/matches` once per competition.
    """
    def _do_get(url, **kwargs):
        matches = [m for m in sample_response["matches"] if f"/competitions/{m['competition']['code']}/matches" in url]
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"matches": matches}
        resp.raise_for_status.return_value = None
        return resp
    return _do_get


def test_normalize_match_uses_shortname():
    match = {
        "id": 1,
        "utcDate": "2026-05-12T19:00:00Z",
        "competition": {"code": "PL", "name": "Premier League"},
        "season": {"startDate": "2025-08-15", "endDate": "2026-05-24"},
        "homeTeam": {"name": "Arsenal FC", "shortName": "Arsenal"},
        "awayTeam": {"name": "Liverpool FC", "shortName": "Liverpool"},
        "matchday": 37,
    }
    out = _normalize_match(match)
    assert out["home"] == "Arsenal"
    assert out["away"] == "Liverpool"
    assert out["competition_group"] == "big5"
    assert out["matchday"] == "Matchday 37"
    assert out["season"] == "2025-2026"


def test_normalize_match_returns_none_for_unknown_competition():
    match = {
        "id": 1,
        "utcDate": "2026-05-12T19:00:00Z",
        "competition": {"code": "ZZZ", "name": "?"},
        "homeTeam": {"name": "A"},
        "awayTeam": {"name": "B"},
    }
    assert _normalize_match(match) is None


def test_normalize_match_returns_none_for_missing_utcdate():
    match = {
        "id": 1,
        "competition": {"code": "PL", "name": "Premier League"},
        "homeTeam": {"name": "A"},
        "awayTeam": {"name": "B"},
    }
    assert _normalize_match(match) is None


def test_fetch_matches_filters_window(sample_response, now):
    rows = fetch_matches(
        now=now,
        window_days=14,
        api_key="dummy",
        http_get=_stub_get(sample_response),
    )
    # In-window: PL/Arsenal-Liverpool (May 12), PD/Real-Barca (May 15)
    # Out-of-window: CL/May 10 (past), PL/June 15 (beyond)
    homes = {r["home"] for r in rows}
    assert homes == {"Arsenal", "Real Madrid"}


def test_build_bundle_sorts_and_serializes(sample_response, now, monkeypatch):
    monkeypatch.setattr("scripts.build_fixtures.requests.get", _stub_get(sample_response))
    bundle = build_bundle(now=now, window_days=14, api_key="dummy")
    assert bundle["window_days"] == 14
    assert bundle["generated_at"].endswith("Z")
    kickoffs = [f["kickoff_utc"] for f in bundle["fixtures"]]
    assert kickoffs == sorted(kickoffs)
    for f in bundle["fixtures"]:
        assert f["kickoff_utc"].endswith("Z")


def test_build_bundle_returns_empty_without_api_key(now):
    bundle = build_bundle(now=now, window_days=14, api_key="")
    assert bundle["fixtures"] == []


def test_build_bundle_returns_empty_when_fetch_raises(now, monkeypatch):
    def boom(*a, **kw):
        raise RuntimeError("network down")
    monkeypatch.setattr("scripts.build_fixtures.requests.get", boom)
    bundle = build_bundle(now=now, window_days=14, api_key="dummy")
    assert bundle["fixtures"] == []


def test_cli_writes_validated_json(tmp_path, sample_response, monkeypatch):
    monkeypatch.setattr("scripts.build_fixtures.requests.get", _stub_get(sample_response))
    monkeypatch.setenv("FOOTBALL_DATA_API_KEY", "dummy")
    out = tmp_path / "fixtures.json"

    rc = run_cli(["--out", str(out), "--window-days", "14"])
    assert rc == 0

    data = json.loads(out.read_text())
    schema = json.loads(
        (Path(__file__).parent.parent / "schema" / "fixtures.schema.json").read_text()
    )
    jsonschema.validate(data, schema)
    assert data["window_days"] == 14
    assert len(data["fixtures"]) >= 1
