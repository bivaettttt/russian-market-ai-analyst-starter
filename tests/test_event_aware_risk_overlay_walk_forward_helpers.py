from app.services.event_aware_risk_overlay_walk_forward import (
    apply_overlay_config_to_sample,
    calculate_overlay_weighted_metrics,
    generate_event_risk_overlay_configs,
    recommendation_from_overlay_summary,
    select_best_overlay_config,
)


def _sample(ret: float, score: float = 65.0, outcome: str | None = None):
    return {
        "date": "2024-01-01",
        "ticker": "SBER",
        "event_family": "rates",
        "event_direction": "negative",
        "event_confirmation": "conflict",
        "event_score": -40,
        "event_risk_score": score,
        "trade_return_pct": ret,
        "outcome": outcome or ("target_hit" if ret > 0 else "stop_hit"),
    }


def test_generate_event_risk_overlay_configs_deterministic_and_limited():
    first = generate_event_risk_overlay_configs(max_configs=10)
    second = generate_event_risk_overlay_configs(max_configs=10)
    assert first == second
    assert len(first) == 10
    assert first[0]["config_id"] == "disabled"


def test_apply_overlay_config_to_sample_uses_risk_level_multiplier():
    config = {
        "config_id": "test",
        "moderate_threshold": 20,
        "elevated_threshold": 40,
        "high_threshold": 60,
        "extreme_threshold": 80,
        "moderate_multiplier": 0.75,
        "elevated_multiplier": 0.5,
        "high_multiplier": 0.35,
        "extreme_multiplier": 0.25,
        "winner_miss_penalty": 1.0,
        "min_multiplier": 0.25,
    }
    row = apply_overlay_config_to_sample(_sample(-2.0, score=65), config=config)
    assert row["event_risk_level"] == "high"
    assert row["position_multiplier"] == 0.35
    assert row["weighted_return_pct"] == -0.7
    assert row["exposure_reduction_pct"] == 65.0
    assert row["avoided_loss_exposure_pct"] == 1.3


def test_calculate_overlay_weighted_metrics_handles_weighted_pf_and_zero_losses():
    rows = [
        {"baseline_return_pct": 2.0, "weighted_return_pct": 1.0, "position_multiplier": 0.5, "outcome": "target_hit", "event_risk_level": "elevated"},
        {"baseline_return_pct": -1.0, "weighted_return_pct": -0.25, "position_multiplier": 0.25, "outcome": "stop_hit", "event_risk_level": "high"},
    ]
    metrics = calculate_overlay_weighted_metrics(rows)
    assert metrics["overlay_weighted_profit_factor"] == 4.0
    assert metrics["baseline_profit_factor"] == 2.0
    assert metrics["samples"] == 2

    no_losses = calculate_overlay_weighted_metrics(
        [{"baseline_return_pct": 1.0, "weighted_return_pct": 0.5, "position_multiplier": 0.5, "outcome": "target_hit", "event_risk_level": "low"}]
    )
    assert no_losses["overlay_weighted_profit_factor"] == 0.5


def test_select_best_overlay_config_uses_disabled_when_all_configs_harmful():
    rows = [_sample(2.0, score=90) for _ in range(5)]
    configs = generate_event_risk_overlay_configs(max_configs=6)
    selected, metrics, _ranked, warnings = select_best_overlay_config(rows, configs)
    assert selected["config_id"] == "disabled"
    assert metrics["weighted_return_delta_pct"] == 0.0
    assert warnings


def test_select_best_overlay_config_selects_beneficial_loss_reduction():
    rows = [_sample(-2.0, score=90) for _ in range(5)]
    configs = generate_event_risk_overlay_configs(max_configs=6)
    selected, metrics, _ranked, warnings = select_best_overlay_config(rows, configs)
    assert selected["config_id"] != "disabled"
    assert metrics["weighted_return_delta_pct"] > 0
    assert warnings == []


def test_recommendation_requires_most_folds_to_improve():
    summary = {
        "event_samples": 500,
        "folds_requested": 4,
        "folds_completed": 4,
        "positive_return_delta_folds": 3,
        "positive_pf_delta_folds": 3,
        "avg_weighted_return_delta_pct": 0.2,
        "avg_weighted_profit_factor_delta": 0.1,
        "avg_position_multiplier": 0.6,
    }
    assert recommendation_from_overlay_summary(summary) == "promising_soft_overlay"
    summary["positive_pf_delta_folds"] = 1
    assert recommendation_from_overlay_summary(summary) == "research_only"
    summary["event_samples"] = 10
    assert recommendation_from_overlay_summary(summary) == "needs_more_data"
