"""Build the DinoStream fixtures JSON from soccerdata sources."""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import math
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, Optional


SEASON_ROLLOVER_MONTH = 8  # August: new season begins


def current_season(now: datetime) -> str:
    """Return the season string covering `now`, e.g. '2025-2026'.

    August onward = new season starting that year.
    """
    if now.month >= SEASON_ROLLOVER_MONTH:
        start = now.year
    else:
        start = now.year - 1
    return f"{start}-{start + 1}"


def filter_window(
    rows: Iterable[dict], now: datetime, window_days: int
) -> list[dict]:
    """Keep only rows whose kickoff_utc is in [now, now + window_days]."""
    end = now + timedelta(days=window_days)
    out: list[dict] = []
    for row in rows:
        ko = row.get("kickoff_utc")
        if ko is None:
            continue
        if now <= ko <= end:
            out.append(row)
    return out


def _parse_kickoff(date_str: Optional[str], time_str: Optional[str]) -> Optional[datetime]:
    """Combine FBref's date+time strings into a UTC datetime, or None if either is missing."""
    if not date_str or not time_str:
        return None
    time_with_seconds = time_str if time_str.count(":") >= 2 else f"{time_str}:00"
    try:
        return datetime.fromisoformat(f"{date_str}T{time_with_seconds}").replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def _is_missing(value) -> bool:
    if value is None or value == "":
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    return False


def _fixture_id(raw: dict, competition_group: str) -> str:
    """Deterministic ID from soccerdata game_id, with hashed fallback."""
    gid = raw.get("game_id")
    if gid:
        return f"fbref-{competition_group}-{gid}"
    fallback = f"{raw.get('league','')}|{raw.get('season','')}|{raw.get('date','')}|{raw.get('home_team','')}|{raw.get('away_team','')}"
    digest = hashlib.sha1(fallback.encode("utf-8")).hexdigest()[:12]
    return f"fbref-{competition_group}-{digest}"


def normalize_row(raw: dict, *, competition: str, competition_group: str) -> dict:
    """Project a soccerdata row dict to the output schema. Optional fields omitted when absent."""
    kickoff = _parse_kickoff(raw.get("date"), raw.get("time"))
    out: dict = {
        "id": _fixture_id(raw, competition_group),
        "kickoff_utc": kickoff,
        "competition": competition,
        "competition_group": competition_group,
        "season": raw.get("season") or "",
        "home": raw.get("home_team") or "",
        "away": raw.get("away_team") or "",
    }
    week = raw.get("week")
    if not _is_missing(week):
        out["matchday"] = f"Matchday {week}"
    venue = raw.get("venue")
    if venue:
        out["venue"] = venue
    return out


import soccerdata as sd
import pandas as pd


BIG5_LEAGUE_MAP = {
    "ENG-Premier League": "Premier League",
    "ESP-La Liga": "La Liga",
    "GER-Bundesliga": "Bundesliga",
    "ITA-Serie A": "Serie A",
    "FRA-Ligue 1": "Ligue 1",
}


logger = logging.getLogger(__name__)


CUP_LEAGUE_MAP = {
    "INT-Champions League": "UEFA Champions League",
    "INT-Europa League": "UEFA Europa League",
    "INT-Europa Conference League": "UEFA Conference League",
}

INTERNATIONAL_LEAGUE_MAP = {
    "INT-World Cup": "FIFA World Cup",
    "INT-European Championship": "UEFA European Championship",
}


SOURCES = [
    ("big5", BIG5_LEAGUE_MAP),
    ("cup", CUP_LEAGUE_MAP),
    ("international", INTERNATIONAL_LEAGUE_MAP),
]


def _isoformat_utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_bundle(*, now: datetime, window_days: int) -> dict:
    """Run all sources and return the bundle dict ready for JSON serialization.

    Failure in any single source is logged and skipped; the bundle is still emitted.
    """
    season = current_season(now)
    all_fixtures: list[dict] = []

    for group, league_map in SOURCES:
        if not league_map:
            continue
        try:
            rows = fetch_competition(
                source="fbref",
                leagues=list(league_map.keys()),
                season=season,
                now=now,
                window_days=window_days,
                league_to_competition=league_map,
                competition_group=group,
            )
            all_fixtures.extend(rows)
        except Exception as exc:  # noqa: BLE001
            logger.warning("source %s failed: %s", group, exc)

    all_fixtures.sort(key=lambda r: r["kickoff_utc"])
    for r in all_fixtures:
        r["kickoff_utc"] = _isoformat_utc(r["kickoff_utc"])

    return {
        "generated_at": _isoformat_utc(now),
        "window_days": window_days,
        "fixtures": all_fixtures,
    }


def fetch_competition(
    *,
    source: str,
    leagues: list[str],
    season: str,
    now: datetime,
    window_days: int,
    league_to_competition: dict[str, str],
    competition_group: str,
) -> list[dict]:
    """Fetch a schedule via soccerdata, normalize, and filter to window.

    Currently supports source='fbref'. Returns a list of dicts in output shape.
    """
    if source != "fbref":
        raise ValueError(f"unsupported source: {source}")

    fbref = sd.FBref(leagues=leagues, seasons=[season])
    df = fbref.read_schedule()
    if isinstance(df.index, pd.MultiIndex):
        df = df.reset_index()

    normalized: list[dict] = []
    for record in df.to_dict(orient="records"):
        league = record.get("league")
        competition = league_to_competition.get(league, league or "Unknown")
        normalized.append(
            normalize_row(record, competition=competition, competition_group=competition_group)
        )

    return filter_window(normalized, now, window_days)


def run_cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build dinostream fixtures.json")
    parser.add_argument("--out", type=Path, required=True, help="Output JSON path")
    parser.add_argument("--window-days", type=int, default=14)
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    now = datetime.now(timezone.utc).replace(microsecond=0)
    bundle = build_bundle(now=now, window_days=args.window_days)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(bundle, indent=2) + "\n")
    logger.info("wrote %d fixtures to %s", len(bundle["fixtures"]), args.out)

    if not bundle["fixtures"]:
        logger.warning("no fixtures emitted — every source failed or returned empty")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(run_cli())
