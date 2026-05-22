from app.services.consumer_signals import (
    apply_ml_v2_experimental_gate_to_decision,
    normalize_ml_v2_gate_mode,
)


def _decision(action: str) -> dict:
    return {
        "action": action,
        "recommendation": "Рассмотреть покупку",
        "decision": "candidate",
        "decision_level": "positive",
        "is_buy_candidate": True,
    }


def _gate(status: str) -> dict:
    return {
        "status": status,
        "probability_pct": 54.0 if status == "rejected" else 56.0,
        "threshold_pct": 55.0,
        "reason": "mock gate",
    }


def test_soft_downgrade_rejected_buy_to_watch():
    updated, meta = apply_ml_v2_experimental_gate_to_decision(
        _decision("buy"),
        ml_v2_research_gate=_gate("rejected"),
        ml_v2_gate_mode="soft_downgrade",
        scenario_direction="long",
    )

    assert updated["action"] == "watch_ml_v2_rejected"
    assert updated["recommendation"] == "Наблюдать"
    assert meta["effect"] == "soft_downgraded"
    assert meta["final_action_changed"] is True


def test_hard_gate_rejected_buy_to_avoid():
    updated, meta = apply_ml_v2_experimental_gate_to_decision(
        _decision("consider_buy"),
        ml_v2_research_gate=_gate("rejected"),
        ml_v2_gate_mode="hard_gate",
        scenario_direction="long",
    )

    assert updated["action"] == "avoid_ml_v2_rejected"
    assert updated["recommendation"] == "Не покупать"
    assert meta["effect"] == "hard_rejected"


def test_diagnostic_only_never_changes_action():
    updated, meta = apply_ml_v2_experimental_gate_to_decision(
        _decision("buy"),
        ml_v2_research_gate=_gate("rejected"),
        ml_v2_gate_mode="diagnostic_only",
        scenario_direction="long",
    )

    assert updated["action"] == "buy"
    assert meta["effect"] == "diagnostic_warning"
    assert meta["final_action_changed"] is False


def test_not_available_never_changes_action():
    updated, meta = apply_ml_v2_experimental_gate_to_decision(
        _decision("buy"),
        ml_v2_research_gate=_gate("not_available"),
        ml_v2_gate_mode="hard_gate",
        scenario_direction="long",
    )

    assert updated["action"] == "buy"
    assert meta["effect"] == "none_not_available"
    assert meta["final_action_changed"] is False


def test_avoid_action_is_not_upgraded_or_changed():
    updated, meta = apply_ml_v2_experimental_gate_to_decision(
        _decision("avoid"),
        ml_v2_research_gate=_gate("passed"),
        ml_v2_gate_mode="hard_gate",
        scenario_direction="downside",
    )

    assert updated["action"] == "avoid"
    assert meta["effect"] == "passed_no_change"
    assert meta["final_action_changed"] is False


def test_invalid_mode_defaults_to_diagnostic_only():
    assert normalize_ml_v2_gate_mode("invalid") == "diagnostic_only"

    updated, meta = apply_ml_v2_experimental_gate_to_decision(
        _decision("buy"),
        ml_v2_research_gate=_gate("rejected"),
        ml_v2_gate_mode="invalid",
        scenario_direction="long",
    )

    assert updated["action"] == "buy"
    assert meta["mode"] == "diagnostic_only"

