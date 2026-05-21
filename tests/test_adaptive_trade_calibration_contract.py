from app.services.adaptive_trade_calibration import (
    build_adaptive_trade_calibration,
    score_trade_policy_metrics,
)


def test_adaptive_trade_calibration_builder_is_callable():
    assert callable(build_adaptive_trade_calibration)


def test_trade_policy_score_prefers_better_outcomes():
    good = {
        "samples": 120,
        "coverage_pct": 70,
        "target_hit_rate_pct": 45,
        "stop_hit_rate_pct": 25,
        "timeout_rate_pct": 30,
        "avg_forward_return_pct": 1.5,
        "avg_mfe_pct": 5.0,
        "avg_mae_pct": -2.0,
    }
    bad = {
        "samples": 120,
        "coverage_pct": 70,
        "target_hit_rate_pct": 20,
        "stop_hit_rate_pct": 65,
        "timeout_rate_pct": 15,
        "avg_forward_return_pct": -1.0,
        "avg_mfe_pct": 2.0,
        "avg_mae_pct": -5.0,
    }

    assert score_trade_policy_metrics(good, min_samples_per_policy=30) > score_trade_policy_metrics(
        bad,
        min_samples_per_policy=30,
    )
