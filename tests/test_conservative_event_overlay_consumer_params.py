from app.services.consumer_signals import _event_overlay_position_fields, normalize_conservative_event_overlay_mode
from app.services.event_aware_risk_overlay import apply_event_risk_overlay_to_signal


def test_conservative_default_mode_is_soft_adjust():
    assert normalize_conservative_event_overlay_mode(None) == "soft_adjust"


def test_position_fields_do_not_overwrite_base_size():
    fields = _event_overlay_position_fields({"max_position_pct": 4.0}, 0.65)
    assert fields["base_position_size_pct"] == 4.0
    assert fields["event_adjusted_position_size_pct"] == 2.6
    assert fields["event_position_delta_pct"] == -1.4


def test_conservative_soft_adjust_keeps_action_unchanged():
    forecast = {"action": "buy", "consumer_action": "buy", "position_sizing": {"max_position_pct": 4.0}}
    overlay = {
        "risk_score": 70,
        "risk_level": "high",
        "position_multiplier": 0.65,
        "min_probability_addon_pct": 8,
        "min_rr_multiplier": 1.35,
        "matched_rule_ids": ["event_score_abs_ge_15_any_setup"],
        "risk_reasons": ["test"],
        "research_basis": "research",
    }
    result = apply_event_risk_overlay_to_signal(forecast=forecast, overlay=overlay, mode="soft_adjust")
    assert result["action"] == "buy"
    assert result["consumer_action"] == "buy"
    assert result["event_risk_final_action_changed"] is False
    assert result["event_risk_action_effect"] == "soft_adjusted"
