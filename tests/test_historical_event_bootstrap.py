from app.services.historical_event_bootstrap import (
    bootstrap_historical_events,
    import_historical_events_from_file,
    normalize_seed_event,
    _summary,
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
    assert event["source"] == "curated_seed"


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


def test_bootstrap_summary_includes_v2_breakdowns():
    result = _summary(
        seed_path="seed.json",
        dry_run=True,
        loaded=2,
        valid_events=[
            {
                "date": "2024-01-15",
                "event_family": "rates",
                "direction": "positive",
                "source": "curated_seed_v2",
            },
            {
                "date": "2025-02-10",
                "event_family": "fx",
                "direction": "mixed",
                "source": "curated_seed",
            },
        ],
        inserted=2,
        updated=0,
        skipped=0,
        errors=[],
        warnings=[],
    )
    assert result["by_year"] == {"2024": 1, "2025": 1}
    assert result["by_source"] == {"curated_seed_v2": 1, "curated_seed": 1}
    assert result["date_range"] == {"first_date": "2024-01-15", "last_date": "2025-02-10"}
