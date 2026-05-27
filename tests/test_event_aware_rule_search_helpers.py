from app.services.event_aware_rule_search import (
    concentration_diagnostics,
    enrich_event_rule_sample,
    generate_event_aware_rules,
    rule_search_recommendation,
    sample_matches_event_rule,
)
from app.services.event_aware_walk_forward import create_walk_forward_folds


def test_sample_matches_event_rule_ops():
    sample = {"setup_family": "pullback", "event_score": 25, "event_family": "rates", "event_direction": "negative"}
    assert sample_matches_event_rule(sample, {"conditions": [{"field": "event_family", "op": "==", "value": "rates"}]})
    assert sample_matches_event_rule(sample, {"conditions": [{"field": "event_family", "op": "!=", "value": "fx"}]})
    assert sample_matches_event_rule(sample, {"conditions": [{"field": "event_family", "op": "in", "value": ["rates", "macro"]}]})
    assert sample_matches_event_rule(sample, {"conditions": [{"field": "event_family", "op": "not_in", "value": ["fx"]}]})
    assert sample_matches_event_rule(sample, {"conditions": [{"field": "event_score", "op": ">=", "value": 20}]})
    assert sample_matches_event_rule(sample, {"conditions": [{"field": "event_score", "op": "<=", "value": 25}]})
    assert not sample_matches_event_rule(sample, {"conditions": [{"field": "missing", "op": "==", "value": True}]})


def test_enrich_event_rule_sample_groups_and_candidates():
    row = enrich_event_rule_sample(
        {
            "setup_family": "mean_reversion",
            "event_family": "sanctions",
            "event_direction": "negative",
            "event_confirmation": "conflict",
            "event_score": -35,
            "setup_score": 45,
        }
    )
    assert row["setup_group"] == "rebound_like"
    assert row["event_group"] == "risk_fx"
    assert row["conflict_rebound_candidate"] is True
    assert row["avoid_long_candidate"] is True


def test_generate_event_aware_rules_deterministic_and_limited():
    first = generate_event_aware_rules(max_rules=12)
    second = generate_event_aware_rules(max_rules=12)
    assert first == second
    assert len(first) == 12
    ids = {row["rule_id"] for row in generate_event_aware_rules()}
    assert "confirmed_positive_any_setup" in ids
    assert "conflict_negative_any_setup" in ids
    assert "any_setup_with_any_event" in ids


def test_concentration_diagnostics_flags_top_ticker_event_year():
    rows = [
        {"ticker": "SBER", "event_id": "event_a", "date": "2025-01-01"},
        {"ticker": "SBER", "event_id": "event_a", "date": "2025-01-02"},
        {"ticker": "GAZP", "event_id": "event_b", "date": "2025-01-03"},
    ]
    result = concentration_diagnostics(rows)
    assert result["top_ticker_share_pct"] > 50
    assert result["top_event_share_pct"] > 50
    assert result["top_year_share_pct"] > 70
    assert result["warnings"]


def test_rule_search_fold_split_no_overlap_and_ordered():
    rows = [{"date": f"2025-01-{day:02d}", "ticker": "SBER"} for day in range(1, 21)]
    folds = create_walk_forward_folds(rows, folds=2, train_ratio=0.5, min_train_samples=5, min_test_samples=3)
    assert folds
    for fold in folds:
        train_dates = {row["date"] for row in fold["train_rows"]}
        test_dates = {row["date"] for row in fold["test_rows"]}
        assert train_dates.isdisjoint(test_dates)
        assert max(train_dates) < min(test_dates)


def test_rule_search_recommendation_requires_stability_and_samples():
    promising = {
        "event_samples": 500,
        "folds_completed": 4,
        "positive_folds": 3,
        "avg_test_selected_profit_factor": 1.2,
        "avg_test_selected_return_pct": 0.4,
        "avg_selected_samples_per_fold": 30,
        "min_signals": 20,
    }
    assert rule_search_recommendation(promising, concentration_warning=False) == "promising_generalized_event_rule"
    assert rule_search_recommendation(promising, concentration_warning=True) == "research_only"
    sparse = dict(promising, event_samples=20)
    assert rule_search_recommendation(sparse, concentration_warning=False) == "needs_more_data"
