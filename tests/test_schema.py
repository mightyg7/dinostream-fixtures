import json
from pathlib import Path

import jsonschema


SCHEMA_PATH = Path(__file__).parent.parent / "schema" / "fixtures.schema.json"


def load_schema():
    return json.loads(SCHEMA_PATH.read_text())


def test_valid_minimal_bundle_passes():
    schema = load_schema()
    bundle = {
        "generated_at": "2026-05-11T06:00:00Z",
        "window_days": 14,
        "fixtures": [
            {
                "id": "fbref-2025-26-eng-prem-1234",
                "kickoff_utc": "2026-05-12T19:00:00Z",
                "competition": "Premier League",
                "competition_group": "big5",
                "season": "2025-2026",
                "home": "Arsenal",
                "away": "Liverpool",
            }
        ],
    }
    jsonschema.validate(bundle, schema)  # raises if invalid


def test_unknown_competition_group_fails():
    schema = load_schema()
    bundle = {
        "generated_at": "2026-05-11T06:00:00Z",
        "window_days": 14,
        "fixtures": [
            {
                "id": "x",
                "kickoff_utc": "2026-05-12T19:00:00Z",
                "competition": "Premier League",
                "competition_group": "bogus",
                "season": "2025-2026",
                "home": "Arsenal",
                "away": "Liverpool",
            }
        ],
    }
    try:
        jsonschema.validate(bundle, schema)
    except jsonschema.ValidationError:
        return
    raise AssertionError("expected ValidationError for unknown competition_group")


def test_missing_required_field_fails():
    schema = load_schema()
    bundle = {
        "generated_at": "2026-05-11T06:00:00Z",
        "window_days": 14,
        "fixtures": [
            {
                "id": "x",
                "kickoff_utc": "2026-05-12T19:00:00Z",
                "competition": "Premier League",
                "competition_group": "big5",
                "home": "Arsenal",
                "away": "Liverpool",
            }
        ],
    }
    try:
        jsonschema.validate(bundle, schema)
    except jsonschema.ValidationError:
        return
    raise AssertionError("expected ValidationError for missing season")
