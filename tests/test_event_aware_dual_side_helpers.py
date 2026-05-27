from app.services.event_aware_dual_side_research import (
    _baseline_metrics,
    _dual_metrics,
    _filter_impact,
    dual_side_walk_forward_recommendation,
    enrich_downside_outcomes,
)


def test_enrich_downside_outcomes_negative_return_creates_avoid_benefit():
    row = enrich_downside_outcomes({"trade_return_pct": -2.5, "outcome": "stop_hit", "mae_pct": -3.0})
    assert row["long_stop_hit_flag"] is True
    assert row["downside_flag"] is True
    assert row["avoid_long_benefit_pct"] == 2.5
    assert row["missed_upside_pct"] == 0.0


def test_enrich_downside_outcomes_positive_return_creates_missed_upside():
    row = enrich_downside_outcomes({"trade_return_pct": 1.7, "outcome": "target_hit", "mae_pct": -0.5})
    assert row["long_target_hit_flag"] is True
    assert row["avoid_long_benefit_pct"] == 0.0
    assert row["missed_upside_pct"] == 1.7


def test_dual_metrics_recommends_avoid_long_for_bad_rule():
    rows = [
        enrich_downside_outcomes({"ticker": f"T{i}", "event_id": f"e{i}", "date": f"{2022 + i % 4}-01-{i+1:02d}", "trade_return_pct": -1.5, "outcome": "stop_hit", "mae_pct": -2.5})
        for i in range(8)
    ]
    baseline = _baseline_metrics(rows + [enrich_downside_outcomes({"ticker": "GAZP", "event_id": "win", "date": "2025-02-01", "trade_return_pct": 2.0, "outcome": "target_hit", "mae_pct": -0.2}) for _ in range(8)])
    metrics = _dual_metrics(rows, baseline=baseline, min_signals=5)
    assert metrics["recommended_use"] == "avoid_long"
    assert metrics["quality_label"] in {"good", "medium"}


def test_dual_metrics_rejects_rule_that_avoids_winners():
    rows = [
        enrich_downside_outcomes({"ticker": f"T{i}", "event_id": f"e{i}", "date": f"{2022 + i % 4}-01-{i+1:02d}", "trade_return_pct": 1.5, "outcome": "target_hit", "mae_pct": -0.3})
        for i in range(8)
    ]
    baseline = _baseline_metrics(rows)
    metrics = _dual_metrics(rows, baseline=baseline, min_signals=5)
    assert metrics["recommended_use"] == "reject"
    assert metrics["quality_label"] == "bad"


def test_filter_impact_blocked_losers_improves_average_return():
    baseline = {"samples": 4, "avg_long_trade_return_pct": 0.0, "long_profit_factor": 1.0, "long_stop_hit_rate_pct": 50.0}
    kept = {"samples": 2, "avg_long_trade_return_pct": 1.0, "long_profit_factor": 2.0, "long_stop_hit_rate_pct": 0.0}
    blocked = [
        {"long_trade_return_pct": -1.0},
        {"long_trade_return_pct": -1.0},
    ]
    impact = _filter_impact(baseline, kept, blocked, 4)
    assert impact["avg_return_delta_pct"] > 0
    assert impact["avoided_losses"] == 2
    assert impact["missed_winners"] == 0


def test_filter_impact_blocked_winners_counts_missed_winners():
    baseline = {"samples": 2, "avg_long_trade_return_pct": 1.0, "long_profit_factor": 2.0, "long_stop_hit_rate_pct": 0.0}
    kept = {"samples": 0, "avg_long_trade_return_pct": None, "long_profit_factor": None, "long_stop_hit_rate_pct": None}
    blocked = [{"long_trade_return_pct": 1.0}, {"long_trade_return_pct": 1.5}]
    impact = _filter_impact(baseline, kept, blocked, 2)
    assert impact["missed_winners"] == 2
    assert impact["missed_upside_pct"] == 2.5


def test_dual_side_walk_forward_recommendation_requires_stable_positive_impact():
    summary = {
        "folds_completed": 4,
        "positive_impact_folds": 3,
        "avg_return_delta_pct": 0.2,
        "avg_profit_factor_delta": 0.1,
        "avg_stop_hit_delta_pct": -5.0,
        "avg_coverage_after_filter_pct": 70.0,
    }
    assert dual_side_walk_forward_recommendation(summary) == "promising_risk_filter"
    assert dual_side_walk_forward_recommendation(dict(summary, positive_impact_folds=1)) == "research_only"
