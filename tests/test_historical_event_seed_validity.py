import json
from datetime import datetime
from pathlib import Path


SEED_PATH = Path("backend/app/data/seed/historical_events_seed.json")


def test_historical_event_seed_valid_json_and_coverage():
    assert SEED_PATH.exists()
    data = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    assert isinstance(data, list)
    assert len(data) >= 50
    dates = [datetime.strptime(row["date"], "%Y-%m-%d").date() for row in data]
    assert min(dates).year <= 2022
    assert max(dates).year >= 2026


def test_historical_event_seed_required_fields_and_unique_ids():
    data = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    ids = [row.get("event_id") for row in data if row.get("event_id")]
    assert len(ids) == len(set(ids))
    for row in data:
        assert row.get("title")
        assert row.get("date")
        assert row.get("direction")
        assert row.get("event_family") or row.get("tags")
