"""Build the DinoStream fixtures JSON from football-data.org."""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

import requests


logger = logging.getLogger(__name__)


SEASON_ROLLOVER_MONTH = 8

# football-data.org competition code -> (display name, competition_group)
COMPETITIONS: dict[str, tuple[str, str]] = {
    "PL":  ("Premier League",               "big5"),
    "PD":  ("La Liga",                      "big5"),
    "BL1": ("Bundesliga",                   "big5"),
    "SA":  ("Serie A",                      "big5"),
    "FL1": ("Ligue 1",                      "big5"),
    "CL":  ("UEFA Champions League",        "cup"),
    "EL":  ("UEFA Europa League",           "cup"),
    "WC":  ("FIFA World Cup",               "international"),
    "EC":  ("UEFA European Championship",   "international"),
}

API_BASE = "https://api.football-data.org/v4"


def current_season(now: datetime) -> str:
    if now.month >= SEASON_ROLLOVER_MONTH:
        start = now.year
    else:
        start = now.year - 1
    return f"{start}-{start + 1}"


def filter_window(rows: Iterable[dict], now: datetime, window_days: int) -> list[dict]:
    end = now + timedelta(days=window_days)
    out: list[dict] = []
    for row in rows:
        ko = row.get("kickoff_utc")
        if ko is None:
            continue
        if now <= ko <= end:
            out.append(row)
    return out


def _isoformat_utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _season_str(season_obj: dict | None) -> str:
    if not season_obj:
        return ""
    start = (season_obj.get("startDate") or "")[:4]
    end = (season_obj.get("endDate") or "")[:4]
    if start and end:
        return f"{start}-{end}"
    return start or end


def _normalize_match(match: dict) -> dict | None:
    """Convert one football-data.org match record to our output schema.

    Returns None if the match is missing required fields.
    """
    utc = match.get("utcDate")
    home = (match.get("homeTeam") or {}).get("shortName") or (match.get("homeTeam") or {}).get("name")
    away = (match.get("awayTeam") or {}).get("shortName") or (match.get("awayTeam") or {}).get("name")
    comp = match.get("competition") or {}
    code = comp.get("code")
    if not utc or not home or not away or not code or code not in COMPETITIONS:
        return None
    try:
        kickoff = datetime.fromisoformat(utc.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None

    comp_name, comp_group = COMPETITIONS[code]
    season_str = _season_str(match.get("season")) or current_season(kickoff)
    out: dict = {
        "id": f"fd-{code}-{match.get('id')}",
        "kickoff_utc": kickoff,
        "competition": comp_name,
        "competition_group": comp_group,
        "season": season_str,
        "home": home,
        "away": away,
    }
    matchday = match.get("matchday")
    if matchday is not None:
        out["matchday"] = f"Matchday {matchday}"
    return out


def fetch_matches(
    *,
    now: datetime,
    window_days: int,
    api_key: str,
    http_get=None,
) -> list[dict]:
    """Query football-data.org per-competition, normalize, filter to window.

    Free tier doesn't expose the multi-competition `/v4/matches` filter, so we
    iterate over each competition's own endpoint and concatenate the results.
    Competitions outside the user's plan return 403 — we skip those.

    `http_get` is an injection point for tests — defaults to requests.get.
    """
    http_get = http_get or requests.get

    date_from = now.date().isoformat()
    date_to = (now + timedelta(days=window_days)).date().isoformat()
    headers = {"X-Auth-Token": api_key}

    all_matches: list[dict] = []
    for code in COMPETITIONS:
        url = f"{API_BASE}/competitions/{code}/matches"
        params = {"dateFrom": date_from, "dateTo": date_to}
        try:
            resp = http_get(url, params=params, headers=headers, timeout=15)
        except Exception as exc:  # noqa: BLE001
            logger.warning("competition %s request failed: %s", code, exc)
            continue
        if resp.status_code in (400, 403, 404):
            logger.info("competition %s not available on this plan (%d)", code, resp.status_code)
            continue
        if not (200 <= resp.status_code < 300):
            logger.warning("competition %s HTTP %d", code, resp.status_code)
            continue
        payload = resp.json()
        all_matches.extend(payload.get("matches", []))

    normalized: list[dict] = []
    for m in all_matches:
        row = _normalize_match(m)
        if row is not None:
            normalized.append(row)

    return filter_window(normalized, now, window_days)


def build_bundle(*, now: datetime, window_days: int, api_key: str | None = None) -> dict:
    """Top-level orchestrator: fetch, sort, serialize."""
    key = api_key if api_key is not None else os.environ.get("FOOTBALL_DATA_API_KEY", "")
    if not key:
        logger.error("FOOTBALL_DATA_API_KEY is not set — cannot fetch fixtures")
        return {
            "generated_at": _isoformat_utc(now),
            "window_days": window_days,
            "fixtures": [],
        }

    try:
        rows = fetch_matches(now=now, window_days=window_days, api_key=key)
    except Exception as exc:  # noqa: BLE001
        logger.warning("football-data.org fetch failed: %s", exc)
        rows = []

    rows.sort(key=lambda r: r["kickoff_utc"])
    for r in rows:
        r["kickoff_utc"] = _isoformat_utc(r["kickoff_utc"])

    return {
        "generated_at": _isoformat_utc(now),
        "window_days": window_days,
        "fixtures": rows,
    }


def run_cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build dinostream fixtures.json")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--window-days", type=int, default=14)
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    now = datetime.now(timezone.utc).replace(microsecond=0)
    bundle = build_bundle(now=now, window_days=args.window_days)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(bundle, indent=2) + "\n")
    logger.info("wrote %d fixtures to %s", len(bundle["fixtures"]), args.out)
    return 0 if bundle["fixtures"] else 1


if __name__ == "__main__":
    sys.exit(run_cli())
