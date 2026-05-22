from app.services.ml_v2_evaluation import build_ml_v2_threshold_report, evaluate_ml_v2_trade_model


def test_evaluate_ml_v2_trade_model_importable_and_callable():
    assert callable(evaluate_ml_v2_trade_model)


def test_threshold_report_pnl_metrics_from_mock_rows():
    rows = [
        {"outcome": "target_hit", "trade_return_pct": 2.0},
        {"outcome": "stop_hit", "trade_return_pct": -1.5},
        {"outcome": "timeout", "trade_return_pct": 0.5},
    ]
    y_true = [1, 0, 1]
    probabilities = [0.8, 0.6, 0.7]
    report = build_ml_v2_threshold_report(rows, y_true, probabilities, thresholds=[0.5, 0.9])
    assert report[0]["signals"] == 3
    assert report[0]["avg_trade_return_pct"] == 0.33
    assert report[0]["profit_factor"] is not None
    assert report[1]["signals"] == 0
    assert report[1]["coverage_pct"] == 0.0
