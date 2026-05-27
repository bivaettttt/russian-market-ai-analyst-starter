from datetime import date

from app.services.event_aware_setup_research import (
    event_coverage_recommendations,
    event_density_score,
)


def test_event_density_score_levels():
    assert event_density_score(0, {}) == "empty"
    assert event_density_score(120, {"2022": 30, "2023": 30}) == "weak"
    assert event_density_score(260, {"2022": 30, "2023": 30, "2024": 30, "2025": 30}) == "medium"
    assert event_density_score(320, {"2022": 60, "2023": 60, "2024": 60, "2025": 60}) == "good"


def test_event_coverage_recommendations_for_sparse_year_and_no_ticker_events():
    recommendations = event_coverage_recommendations(
        total_events=120,
        events_by_year={"2022": 50, "2023": 5},
        by_event_family={"rates": 10},
        events_with_ticker=0,
        dates=[date(2022, 1, 1), date(2023, 1, 1)],
    )
    assert any("250" in item for item in recommendations)
    assert any("2023" in item for item in recommendations)
    assert any("ticker-level" in item for item in recommendations)
