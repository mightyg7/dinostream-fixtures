"""Build the DinoStream fixtures JSON from soccerdata sources."""

from __future__ import annotations

from datetime import datetime, timezone


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
