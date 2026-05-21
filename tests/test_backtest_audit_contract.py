from app.services.consumer_signal_backtest_audit import (
    _calibration_score,
    build_consumer_signal_backtest_audit,
    build_consumer_threshold_sweep_audit,
    build_consumer_walk_forward_validation,
)


def test_backtest_audit_builders_are_callable():
    assert callable(build_consumer_signal_backtest_audit)
    assert callable(build_consumer_threshold_sweep_audit)
    assert callable(build_consumer_walk_forward_validation)


def test_calibration_score_contract():
    score = _calibration_score(
        {
            "samples": 50,
            "target_hit_rate_pct": 40,
            "stop_hit_rate_pct": 30,
            "timeout_rate_pct": 30,
            "avg_forward_return_pct": 1.5,
        },
        min_signals=20,
    )

    assert isinstance(score, float)
    assert -100 <= score <= 100
    assert score > 0
