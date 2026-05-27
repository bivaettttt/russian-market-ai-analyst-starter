from app.services.ml_v3_consumer_candidate_evaluation import (
    build_ml_v3_consumer_candidate_walk_forward,
    evaluate_ml_v3_consumer_candidate_model,
    parse_ml_v3_thresholds,
    score_ml_v3_walk_forward_result,
)


def test_ml_v3_evaluation_contract_importable():
    assert callable(evaluate_ml_v3_consumer_candidate_model)
    assert callable(build_ml_v3_consumer_candidate_walk_forward)


def test_parse_ml_v3_thresholds():
    assert parse_ml_v3_thresholds("40,0.55,bad,70") == [0.4, 0.55, 0.7]


def test_walk_forward_scoring_stability_penalties():
    strong = score_ml_v3_walk_forward_result(
        {
            "avg_selected_trade_return_pct": 0.4,
            "avg_selected_profit_factor": 1.2,
            "avg_trade_return_delta_pct": 0.3,
            "avg_profit_factor_delta": 0.15,
            "stable_positive_rate_pct": 75,
            "positive_folds": 3,
            "negative_folds": 1,
            "avg_stop_hit_delta_pct": -4,
            "total_selected_samples": 100,
            "avg_coverage_pct": 25,
            "folds_with_signals": 4,
        },
        folds=4,
        min_signals=30,
    )
    weak = score_ml_v3_walk_forward_result(
        {
            "avg_selected_trade_return_pct": -0.4,
            "avg_selected_profit_factor": 0.8,
            "avg_trade_return_delta_pct": -0.3,
            "avg_profit_factor_delta": -0.15,
            "stable_positive_rate_pct": 0,
            "positive_folds": 0,
            "negative_folds": 4,
            "avg_stop_hit_delta_pct": 4,
            "total_selected_samples": 5,
            "avg_coverage_pct": 2,
            "folds_with_signals": 1,
        },
        folds=4,
        min_signals=30,
    )
    assert strong > weak
