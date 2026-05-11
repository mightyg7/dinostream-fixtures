"""Build the DinoStream fixtures JSON from soccerdata sources."""

from __future__ import annotations

import hashlib
import math
from datetime import datetime, timedelta, timezone
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
