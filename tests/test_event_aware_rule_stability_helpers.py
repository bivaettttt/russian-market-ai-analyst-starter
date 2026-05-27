from app.services.event_aware_rule_stability import (
    concentration_label,
    diagnose_static_to_walk_forward_failure,
    score_rule_stability,
)


def _overall(**overrides):
    data = {
        "samples": 100,
        "score": 30,
        "avg_avoid_long_benefit_pct": 2.0,
        "avg_missed_upside_pct": 1.0,
    }
    data.update(overrides)
    return data


def test_score_rule_stability_stable_multi_year_low_concentration():
    result = score_rule_stability(
        overall_metrics=_overall(),
        by_year=[{"samples": 25, "avg_long_trade_return_pct": -1, "avoid_benefit": 2, "missed_upside": 1, "score": 20} for _ in range(4)],
        by_time_bucket=[{"samples": 25, "avg_long_trade_return_pct": -1, "avoid_benefit": 2, "missed_upside": 1, "score": 20} for _ in range(4)],
        concentration={"top_ticker_share_pct": 20, "top_event_share_pct": 20, "top_year_share_pct": 30, "concentration_label": "low"},
        baseline={},
        min_signals=20,
    )
    assert result["stability_label"] == "stable"
    assert result["year_stability_rate_pct"] == 100


def test_score_rule_stability_rejects_missed_upside_greater_than_avoid_benefit():
    result = score_rule_stability(
        overall_metrics=_overall(avg_avoid_long_benefit_pct=1, avg_missed_upside_pct=2),
        by_year=[{"samples": 25, "avg_long_trade_return_pct": -1, "avoid_benefit": 1, "missed_upside": 2, "score": 20} for _ in range(4)],
        by_time_bucket=[{"samples": 25, "avg_long_trade_return_pct": -1, "avoid_benefit": 1, "missed_upside": 2, "score": 20} for _ in range(4)],
        concentration={"top_ticker_share_pct": 20, "top_event_share_pct": 20, "top_year_share_pct": 30, "concentration_label": "low"},
        baseline={},
        min_signals=20,
    )
    assert result["stability_label"] == "reject"


def test_score_rule_stability_unstable_one_year_dependency():
    result = score_rule_stability(
        overall_metrics=_overall(),
        by_year=[{"samples": 100, "avg_long_trade_return_pct": -1, "avoid_benefit": 2, "missed_upside": 1, "score": 20}],
        by_time_bucket=[{"samples": 25, "avg_long_trade_return_pct": -1, "avoid_benefit": 2, "missed_upside": 1, "score": 20} for _ in range(4)],
        concentration={"top_ticker_share_pct": 20, "top_event_share_pct": 20, "top_year_share_pct": 100, "concentration_label": "extreme"},
        baseline={},
        min_signals=20,
    )
    assert result["stability_label"] == "reject"
    assert result["years_with_samples"] == 1


def test_score_rule_stability_moderate_regime_specific_like_profile():
    result = score_rule_stability(
        overall_metrics=_overall(score=10),
        by_year=[
            {"samples": 30, "avg_long_trade_return_pct": -1, "avoid_benefit": 2, "missed_upside": 1, "score": 10},
            {"samples": 30, "avg_long_trade_return_pct": 1, "avoid_benefit": 1, "missed_upside": 2, "score": -5},
        ],
        by_time_bucket=[
            {"samples": 30, "avg_long_trade_return_pct": -1, "avoid_benefit": 2, "missed_upside": 1, "score": 10},
            {"samples": 30, "avg_long_trade_return_pct": 1, "avoid_benefit": 1, "missed_upside": 2, "score": -5},
        ],
        concentration={"top_ticker_share_pct": 20, "top_event_share_pct": 20, "top_year_share_pct": 50, "concentration_label": "medium"},
        baseline={},
        min_signals=20,
    )
    assert result["stability_label"] in {"moderate", "unstable"}
    assert result["years_with_samples"] == 2


def test_concentration_label_levels():
    assert concentration_label({"top_ticker_share_pct": 10, "top_event_share_pct": 10, "top_year_share_pct": 10}) == "low"
    assert concentration_label({"top_ticker_share_pct": 35, "top_event_share_pct": 10, "top_year_share_pct": 10}) == "medium"
    assert concentration_label({"top_ticker_share_pct": 55, "top_event_share_pct": 10, "top_year_share_pct": 10}) == "high"
    assert concentration_label({"top_ticker_share_pct": 75, "top_event_share_pct": 10, "top_year_share_pct": 10}) == "extreme"


def test_failure_diagnosis_modes():
    winner = diagnose_static_to_walk_forward_failure(
        static_results=[],
        stability_results=[{"failure_modes": ["missed_winners_high"], "stability_label": "reject"}],
    )
    assert winner["primary_failure_reason"] == "winner_miss_rate"

    concentrated = diagnose_static_to_walk_forward_failure(
        static_results=[],
        stability_results=[{"failure_modes": ["one_event_dependency"], "stability_label": "unstable"}],
    )
    assert concentrated["primary_failure_reason"] == "concentration"

    unstable = diagnose_static_to_walk_forward_failure(static_results=[], stability_results=[])
    assert unstable["primary_failure_reason"] == "unknown"
