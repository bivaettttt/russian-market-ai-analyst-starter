import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path


SEED_PATH = Path("backend/app/data/seed/historical_events_seed.json")
ALLOWED_EVENT_FAMILIES = {
    "rates",
    "inflation",
    "macro",
    "fx",
    "oil_gas",
    "commodities",
    "sanctions",
    "geopolitics",
    "dividend",
    "earnings",
    "corporate_action",
    "sector_news",
    "ticker_news",
    "market_structure",
    "unknown",
}
ALLOWED_DIRECTIONS = {"positive", "negative", "mixed", "neutral"}
ALLOWED_SCOPES = {"ticker", "sector", "market", "asset_class", "global"}
ALLOWED_CONFIDENCE = {"low", "medium", "high"}
EVENT_ID_RE = re.compile(r"^[a-z0-9_]+$")


def test_historical_event_seed_valid_json_and_coverage():
    assert SEED_PATH.exists()
    data = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    assert isinstance(data, list)
    assert len(data) >= 250
    dates = [datetime.strptime(row["date"], "%Y-%m-%d").date() for row in data]
    assert min(dates).year <= 2022
    assert max(dates).year >= 2026


def test_historical_event_seed_required_fields_and_unique_ids():
    data = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    ids = [row.get("event_id") for row in data if row.get("event_id")]
    assert len(ids) == len(data)
    assert len(ids) == len(set(ids))
    for row in data:
        assert EVENT_ID_RE.match(row["event_id"])
        assert row.get("title")
        assert row.get("date")
        assert row.get("source")
        assert row.get("direction")
        assert row.get("event_family") or row.get("tags")
        assert row.get("event_family") in ALLOWED_EVENT_FAMILIES
        assert row.get("direction") in ALLOWED_DIRECTIONS
        assert row.get("impact_scope") in ALLOWED_SCOPES
        assert row.get("confidence") in ALLOWED_CONFIDENCE
        assert -100 <= int(row.get("score")) <= 100
        assert isinstance(row.get("tags"), list)
        assert row.get("tags")
        assert isinstance(row.get("affected_sectors"), list)
        assert isinstance(row.get("affected_asset_types"), list)
        assert isinstance(row.get("affected_tickers"), list)


def test_historical_event_seed_v2_distribution():
    data = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    by_year = Counter(datetime.strptime(row["date"], "%Y-%m-%d").date().year for row in data)
    assert by_year[2022] >= 50
    assert by_year[2023] >= 40
    assert by_year[2024] >= 40
    assert by_year[2025] >= 20

    by_family = Counter(row["event_family"] for row in data)
    assert by_family["rates"] >= 10
    assert by_family["fx"] >= 10
    assert by_family["sanctions"] + by_family["geopolitics"] >= 20
    assert (
        by_family["dividend"]
        + by_family["earnings"]
        + by_family["corporate_action"]
        + by_family["ticker_news"]
    ) >= 40
