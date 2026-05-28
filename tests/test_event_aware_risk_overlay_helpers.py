from app.services.event_aware_risk_overlay import (
    apply_event_risk_overlay_to_signal,
    build_event_aware_risk_overlay,
    score_event_risk_overlay,
)
from app.services.event_aware_risk_overlay_backtest import _mode_metrics


def _rule(**overrides):
    row = {
        "rule_id": "stable_rule",
        "recommended_use": "stable_risk_filter",
        "stability_score": 70,
        "avg_avoid_long_benefit_pct": 2.0,
        "avg_missed_upside_pct": 1.0,
        "stop_hit_lift_vs_baseline": 8,
        "failure_modes": [],
    }
    row.update(overrides)
    return row


def test_risk_score_mapping_and_modifiers():
    low = score_event_risk_overlay(matched_rules=[])
    assert low["risk_level"] == "low"

    high = score_event_risk_overlay(
        matched_rules=[_rule(), _rule(rule_id="stable_rule_2")],
        event_context={"event_family": "sanctions", "event_direction": "negative", "event_score": -50},
        market_regime={"regime": "risk_off"},
    )
    assert high["risk_level"] in {"high", "extreme"}

    positive = score_event_risk_overlay(
        matched_rules=[_rule()],
        event_context={"event_direction": "positive", "event_confirmation": "confirmed", "event_score": 40},
        market_regime={"regime": "risk_on"},
    )
    assert positive["risk_score"] < score_event_risk_overlay(matched_rules=[_rule()])["risk_score"]


def test_winner_miss_rate_failure_reduces_contribution():
    clean = score_event_risk_overlay(matched_rules=[_rule()])
    penalized = score_event_risk_overlay(matched_rules=[_rule(failure_modes=["winner_miss_rate"])])
    assert penalized["risk_score"] < clean["risk_score"]


def test_overlay_modes_do_not_change_action_except_experimental_high():
    forecast = {"action": "buy", "consumer_action": "buy", "recommendation": "Покупать", "position_sizing": {"max_position_pct": 5}}
    overlay = build_event_aware_risk_overlay(matched_rules=[_rule(), _rule(rule_id="r2")], threshold_config={"mode": "diagnostic_only"})
    diagnostic = apply_event_risk_overlay_to_signal(forecast=forecast, overlay=overlay, mode="diagnostic_only")
    assert diagnostic["action"] == "buy"
    assert diagnostic["event_risk_final_action_changed"] is False

    soft = apply_event_risk_overlay_to_signal(forecast=forecast, overlay=overlay, mode="soft_adjust")
    assert soft["action"] == "buy"
    assert soft["position_sizing"]["event_risk_adjusted_max_position_pct"] <= 5

    high_overlay = dict(overlay, risk_level="high", risk_score=70, position_multiplier=0.35)
    downgraded = apply_event_risk_overlay_to_signal(
        forecast=forecast,
        overlay=high_overlay,
        mode="experimental_downgrade",
    )
    assert downgraded["action"] == "watch_event_risk"

    avoid = apply_event_risk_overlay_to_signal(
        forecast={"action": "avoid", "consumer_action": "avoid", "position_sizing": {}},
        overlay=high_overlay,
        mode="experimental_downgrade",
    )
    assert avoid["action"] == "avoid"


def test_backtest_weighted_metrics_and_exposure_reduction():
    rows = [
        {"outcome": "target_hit", "trade_return_pct": 2.0, "position_multiplier": 0.5},
        {"outcome": "stop_hit", "trade_return_pct": -2.0, "position_multiplier": 0.25},
    ]
    metrics = _mode_metrics(rows, mode="soft_adjust")
    assert metrics["overlay_weighted_avg_return_pct"] == 0.25
    assert metrics["exposure_reduction_pct"] == 62.5
    assert metrics["overlay_weighted_profit_factor"] == 2.0
