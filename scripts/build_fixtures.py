"""Build the DinoStream fixtures JSON from soccerdata sources."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Iterable


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
