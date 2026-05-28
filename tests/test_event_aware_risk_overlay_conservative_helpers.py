from app.services.event_aware_risk_overlay_conservative_calibration import (
    conservative_recommendation,
    constraint_status,
    generate_conservative_overlay_configs,
    score_conservative_overlay_metrics,
)


def test_generate_conservative_overlay_configs_includes_benchmarks_and_respects_limit():
    configs = generate_conservative_overlay_configs(max_configs=8)
    ids = [config["config_id"] for config in configs]
    assert len(configs) == 8
    assert ids[0] == "disabled"
    assert "benchmark_aggressive_t15_35_55_m75_e60_h40_x10_w100" in ids
    assert "benchmark_default_soft_overlay" in ids
    conservative = [config for config in configs if config.get("profile") == "conservative"]
    assert conservative
    assert min(config["extreme_multiplier"] for config in conservative) >= 0.4


def test_score_conservative_overlay_metrics_rewards_balanced_improvement():
    result = score_conservative_overlay_metrics(
        {
            "weighted_return_delta_pct": 0.2,
            "weighted_profit_factor_delta": 0.15,
            "stop_hit_exposure_delta_pct": -3.0,
            "avg_position_multiplier": 0.62,
            "exposure_reduction_pct": 38.0,
        }
    )
    assert result["conservative_score"] > 0
    assert result["quality_label"] == "good"


def test_score_conservative_overlay_metrics_penalizes_aggressive_cut():
    result = score_conservative_overlay_metrics(
        {
            "weighted_return_delta_pct": 0.2,
            "weighted_profit_factor_delta": 0.15,
            "stop_hit_exposure_delta_pct": -3.0,
            "avg_position_multiplier": 0.29,
            "exposure_reduction_pct": 71.0,
        }
    )
    assert result["quality_label"] == "bad"
    assert result["conservative_score"] < 0


def test_constraint_status():
    passed = constraint_status(
        {"avg_position_multiplier": 0.55, "exposure_reduction_pct": 45},
        min_avg_position_multiplier=0.5,
        max_exposure_reduction_pct=50,
    )
    assert passed == {"passes_min_multiplier": True, "passes_max_exposure_reduction": True}
    failed = constraint_status(
        {"avg_position_multiplier": 0.4, "exposure_reduction_pct": 60},
        min_avg_position_multiplier=0.5,
        max_exposure_reduction_pct=50,
    )
    assert failed == {"passes_min_multiplier": False, "passes_max_exposure_reduction": False}


def test_conservative_recommendation():
    summary = {
        "samples": 500,
        "event_samples": 450,
        "folds_completed": 4,
        "avg_position_multiplier": 0.55,
        "avg_exposure_reduction_pct": 45,
        "positive_pf_delta_folds": 3,
        "avg_weighted_profit_factor_delta": 0.1,
        "avg_stop_hit_exposure_delta_pct": -2,
        "positive_return_delta_folds": 2,
    }
    assert conservative_recommendation(summary, min_positive_pf_folds=3) == "conservative_overlay_candidate"
    summary["avg_position_multiplier"] = 0.3
    assert conservative_recommendation(summary, min_positive_pf_folds=3) == "research_only"
    summary["avg_weighted_profit_factor_delta"] = -0.1
    summary["avg_stop_hit_exposure_delta_pct"] = 1
    summary["positive_pf_delta_folds"] = 0
    assert conservative_recommendation(summary, min_positive_pf_folds=3) == "reject"
