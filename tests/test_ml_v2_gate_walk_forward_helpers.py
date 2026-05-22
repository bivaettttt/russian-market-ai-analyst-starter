from app.services.ml_v2_gate_walk_forward import (
    aggregate_gate_walk_forward_results,
    build_gate_walk_forward_ranges,
    classify_gate_walk_forward_quality,
    parse_gate_walk_forward_modes,
    parse_gate_walk_forward_thresholds,
    score_gate_walk_forward_summary,
)


def test_parse_thresholds_and_gate_modes_are_reused_safely():
    assert parse_gate_walk_forward_thresholds("0.5,55,0.60,bad") == [0.5, 0.55, 0.6]
    assert parse_gate_walk_forward_modes("hard_gate,invalid,soft_downgrade") == ["hard_gate", "soft_downgrade"]


def test_fold_ranges_do_not_overlap_train_and_test():
    ranges = build_gate_walk_forward_ranges(
        total=1000,
        folds=3,
        train_ratio=0.6,
        min_train_samples=100,
        min_test_samples=100,
    )
    assert ranges
    for train_start, train_end, test_end in ranges:
        assert train_start == 0
        assert train_end < test_end


def test_gate_walk_forward_quality_labels():
    stable = {
        "total_selected_samples": 120,
        "folds_with_signals": 3,
        "avg_coverage_pct": 25,
        "avg_selected_trade_return_pct": 0.2,
        "avg_selected_profit_factor": 1.12,
        "stable_positive_rate_pct": 66.7,
    }
    unstable = {**stable, "total_selected_samples": 5, "avg_coverage_pct": 2}

    assert classify_gate_walk_forward_quality(stable, folds_requested=4, min_signals=50) == "stable"
    assert classify_gate_walk_forward_quality(unstable, folds_requested=4, min_signals=50) == "unstable"


def test_gate_walk_forward_score_rewards_better_metrics():
    weak = {
        "avg_selected_trade_return_pct": -0.1,
        "avg_selected_profit_factor": 0.9,
        "avg_trade_return_delta_pct": 0,
        "avg_profit_factor_delta": 0,
        "stable_positive_rate_pct": 0,
        "positive_folds": 0,
        "negative_folds": 3,
        "avg_stop_hit_delta_pct": 0,
        "total_selected_samples": 100,
        "avg_coverage_pct": 30,
        "folds_with_signals": 3,
    }
    better = {
        **weak,
        "avg_selected_trade_return_pct": 0.3,
        "avg_selected_profit_factor": 1.2,
        "avg_trade_return_delta_pct": 0.4,
        "avg_profit_factor_delta": 0.25,
        "stable_positive_rate_pct": 75,
        "positive_folds": 3,
        "negative_folds": 1,
        "avg_stop_hit_delta_pct": -5,
    }

    assert score_gate_walk_forward_summary(better, folds_requested=4, min_signals=50) > score_gate_walk_forward_summary(
        weak, folds_requested=4, min_signals=50
    )


def test_aggregate_gate_walk_forward_results_stable_from_mock_folds():
    fold_row = {
        "gate_mode": "hard_gate",
        "threshold_pct": 55.0,
        "selected_samples": 40,
        "coverage_pct": 20,
        "selected_avg_trade_return_pct": 0.3,
        "selected_profit_factor": 1.2,
        "selected_win_rate_pct": 55,
        "selected_stop_hit_rate_pct": 40,
        "baseline_avg_trade_return_pct": -0.1,
        "avg_trade_return_delta_pct": 0.4,
        "profit_factor_delta": 0.25,
        "win_rate_delta_pct": 5,
        "stop_hit_delta_pct": -5,
        "avoided_losses": 10,
        "missed_wins": 4,
    }
    folds = [{"gate_results": [dict(fold_row)]}, {"gate_results": [dict(fold_row)]}]

    rows = aggregate_gate_walk_forward_results(
        folds,
        thresholds=[0.55],
        gate_modes=["hard_gate"],
        min_signals=50,
    )

    assert rows[0]["total_selected_samples"] == 80
    assert rows[0]["quality_label"] in {"stable", "promising"}
