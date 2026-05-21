from app.services.regime_formula_calibration import (
    build_regime_formula_calibration,
    score_regime_formula_result,
)


def test_regime_formula_calibration_builder_is_callable():
    assert callable(build_regime_formula_calibration)


def test_regime_formula_score_rewards_lower_stop_hit_and_higher_return():
    good = {
        "filtered_signals": 100,
        "coverage_after_filter_pct": 80,
        "stop_hit_delta_pct": -5,
        "avg_return_delta_pct": 1.2,
        "target_hit_delta_pct": 0.5,
        "avoided_stop_hits": 12,
        "missed_target_hits": 2,
    }
    bad = {
        "filtered_signals": 100,
        "coverage_after_filter_pct": 80,
        "stop_hit_delta_pct": 3,
        "avg_return_delta_pct": -0.8,
        "target_hit_delta_pct": -1.0,
        "avoided_stop_hits": 2,
        "missed_target_hits": 10,
    }

    assert score_regime_formula_result(good, min_signals_after_filter=30) > score_regime_formula_result(
        bad,
        min_signals_after_filter=30,
    )
