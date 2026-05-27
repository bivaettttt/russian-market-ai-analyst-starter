from app.services.historical_event_bootstrap import (
    bootstrap_historical_events,
    import_historical_events_from_file,
    normalize_seed_event,
)


def test_historical_event_bootstrap_contract_importable():
    assert callable(bootstrap_historical_events)
    assert callable(import_historical_events_from_file)


def test_normalize_seed_event_lists_and_stable_id():
    event = normalize_seed_event(
        {
            "date": "2024-01-15",
            "title": "Test rate cut",
            "summary": "Rate cut supports bonds",
            "source": "curated_seed",
            "event_family": "rates",
            "direction": "positive",
            "affected_tickers": "SBER, LKOH",
            "affected_sectors": "banks;bonds",
            "tags": "rates,key_rate_down",
        }
    )
    assert event["event_id"].startswith("seed_")
    assert event["date"] == "2024-01-15"
    assert event["affected_tickers"] == ["SBER", "LKOH"]
    assert event["affected_sectors"] == ["banks", "bonds"]
    assert event["tags"] == ["rates", "key_rate_down"]
    assert event["event_family"] == "rates"


def test_normalize_seed_event_preserves_explicit_event_id():
    event = normalize_seed_event(
        {
            "event_id": "custom_event",
            "date": "2024-01-15",
            "title": "Test sanctions relief",
            "tags": ["sanctions_relief"],
            "direction": "positive",
        }
    )
    assert event["event_id"] == "custom_event"
    assert event["event_family"] == "sanctions"
