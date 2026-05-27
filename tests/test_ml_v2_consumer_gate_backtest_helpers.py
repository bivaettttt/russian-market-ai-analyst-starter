from app.services.ml_v2_consumer_gate_backtest import (
    apply_ml_v2_gate_to_historical_action,
    is_long_candidate_action,
    score_ml_v2_consumer_gate_backtest_result,
)


def test_is_long_candidate_action_mapping():
    assert is_long_candidate_action("buy") is True
    assert is_long_candidate_action("consider_buy") is True
    assert is_long_candidate_action("watch_ml_confirmed") is True
    assert is_long_candidate_action("avoid") is False
    assert is_long_candidate_action("avoid_ml_veto") is False


def test_apply_diagnostic_only_no_change():
    result = apply_ml_v2_gate_to_historical_action(
        original_action="buy",
        ml_v2_probability_pct=40.0,
        threshold_pct=55.0,
        gate_mode="diagnostic_only",
    )
    assert result["final_action"] == "buy"
    assert result["action_changed"] is False
    assert result["active_trade"] is True


def test_apply_soft_rejected_buy_removes_active_trade():
    result = apply_ml_v2_gate_to_historical_action(
        original_action="buy",
        ml_v2_probability_pct=40.0,
        threshold_pct=55.0,
        gate_mode="soft_downgrade",
    )
    assert result["final_action"] == "watch_ml_v2_rejected"
    assert result["action_changed"] is True
    assert result["active_trade"] is False


def test_apply_hard_rejected_buy_removes_active_trade():
    result = apply_ml_v2_gate_to_historical_action(
        original_action="buy",
        ml_v2_probability_pct=40.0,
        threshold_pct=55.0,
        gate_mode="hard_gate",
    )
    assert result["final_action"] == "avoid_ml_v2_rejected"
    assert result["action_changed"] is True
    assert result["active_trade"] is False


def test_apply_passed_no_change():
    result = apply_ml_v2_gate_to_historical_action(
        original_action="consider_buy",
        ml_v2_probability_pct=60.0,
        threshold_pct=55.0,
        gate_mode="hard_gate",
    )
    assert result["final_action"] == "consider_buy"
    assert result["action_changed"] is False
    assert result["active_trade"] is True


def test_apply_not_available_no_change():
    result = apply_ml_v2_gate_to_historical_action(
        original_action="buy",
        ml_v2_probability_pct=None,
        threshold_pct=55.0,
        gate_mode="hard_gate",
        ml_v2_status="not_available",
    )
    assert result["final_action"] == "buy"
    assert result["action_changed"] is False
    assert result["active_trade"] is True
    assert result["gate_effect"] == "none_not_available"


def test_scoring_prefers_better_pf_and_return():
    weak = score_ml_v2_consumer_gate_backtest_result(
        selected_avg_trade_return_pct=-0.1,
        selected_profit_factor=0.9,
        avg_trade_return_delta_pct=-0.2,
        profit_factor_delta=-0.1,
        win_rate_delta_pct=-2.0,
        stop_hit_delta_pct=3.0,
        selected_active_trades=100,
        coverage_pct=40.0,
        avoided_losses=5,
        missed_wins=20,
        min_signals=50,
    )
    strong = score_ml_v2_consumer_gate_backtest_result(
        selected_avg_trade_return_pct=0.5,
        selected_profit_factor=1.3,
        avg_trade_return_delta_pct=0.4,
        profit_factor_delta=0.2,
        win_rate_delta_pct=4.0,
        stop_hit_delta_pct=-5.0,
        selected_active_trades=100,
        coverage_pct=40.0,
        avoided_losses=20,
        missed_wins=5,
        min_signals=50,
    )
    assert strong > weak
