from app.services.ml_v2_gate_impact_evaluation import (
    classify_gate_impact_quality,
    parse_gate_impact_thresholds,
    parse_gate_modes,
    score_gate_impact_result,
)


def test_parse_gate_impact_thresholds_accepts_decimal_and_percent():
    assert parse_gate_impact_thresholds("0.5,55,0.60,bad") == [0.5, 0.55, 0.6]


def test_parse_gate_modes_ignores_invalid_values():
    assert parse_gate_modes("hard_gate,unknown,diagnostic_only") == ["hard_gate", "diagnostic_only"]


def test_gate_impact_quality_labels():
    assert (
        classify_gate_impact_quality(
            selected_samples=100,
            selected_profit_factor=1.12,
            selected_avg_trade_return_pct=0.2,
            score=30,
            coverage_pct=25,
            min_signals=50,
        )
        == "good"
    )
    assert (
        classify_gate_impact_quality(
            selected_samples=10,
            selected_profit_factor=2.0,
            selected_avg_trade_return_pct=1.0,
            score=80,
            coverage_pct=3,
            min_signals=50,
        )
        == "unstable"
    )


def test_score_gate_impact_rewards_better_return_and_profit_factor():
    weak = score_gate_impact_result(
        selected_avg_trade_return_pct=-0.1,
        selected_profit_factor=0.9,
        avg_trade_return_delta_pct=0.0,
        profit_factor_delta=0.0,
        win_rate_delta_pct=0.0,
        stop_hit_delta_pct=0.0,
        selected_samples=100,
        coverage_pct=50,
        avoided_losses=0,
        missed_wins=0,
        min_signals=50,
    )
    improved = score_gate_impact_result(
        selected_avg_trade_return_pct=0.25,
        selected_profit_factor=1.15,
        avg_trade_return_delta_pct=0.2,
        profit_factor_delta=0.2,
        win_rate_delta_pct=5.0,
        stop_hit_delta_pct=-4.0,
        selected_samples=100,
        coverage_pct=50,
        avoided_losses=20,
        missed_wins=10,
        min_signals=50,
    )

    assert improved > weak
