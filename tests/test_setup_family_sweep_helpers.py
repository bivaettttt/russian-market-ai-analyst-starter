from app.services.setup_family_research import classify_setup_family_quality, score_setup_config_result


def test_setup_quality_good_and_unstable():
    assert classify_setup_family_quality(samples=50, profit_factor=1.2, avg_trade_return_pct=0.4, min_signals=30) == "good"
    assert classify_setup_family_quality(samples=5, profit_factor=2.0, avg_trade_return_pct=1.0, min_signals=30) == "unstable"


def test_setup_config_score_prefers_better_metrics():
    weak = score_setup_config_result(
        {"samples": 50, "coverage_pct": 20, "avg_trade_return_pct": -0.5, "profit_factor": 0.8, "win_rate_pct": 40, "stop_hit_rate_pct": 60},
        min_signals=30,
    )
    strong = score_setup_config_result(
        {"samples": 50, "coverage_pct": 20, "avg_trade_return_pct": 0.5, "profit_factor": 1.3, "win_rate_pct": 55, "stop_hit_rate_pct": 35},
        min_signals=30,
    )
    assert strong > weak
