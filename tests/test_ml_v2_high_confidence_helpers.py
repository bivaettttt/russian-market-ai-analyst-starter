from app.services.ml_v2_high_confidence_validation import (
    aggregate_threshold_summary,
    parse_thresholds,
    threshold_quality_label,
)


def test_parse_thresholds_ignores_invalid_and_sorts_unique():
    assert parse_thresholds("0.6, bad, 0.55, 1.2, 0.6") == [0.55, 0.6]


def test_parse_thresholds_default_when_empty_or_invalid():
    assert parse_thresholds(None, default=[0.5]) == [0.5]
    assert parse_thresholds("bad", default=[0.5]) == [0.5]


def test_threshold_quality_stable_and_unstable():
    stable = {
        "total_signals": 80,
        "folds_with_signals": 4,
        "avg_trade_return_pct": 0.2,
        "avg_profit_factor": 1.12,
        "stable_positive_rate_pct": 75,
    }
    unstable = {**stable, "total_signals": 12}
    assert threshold_quality_label(stable, requested_folds=4) == "stable"
    assert threshold_quality_label(unstable, requested_folds=4) == "unstable"


def test_aggregate_threshold_summary_no_division_by_zero():
    folds = [
        {
            "threshold_report": [
                {"threshold_pct": 60.0, "signals": 10, "coverage_pct": 5, "avg_trade_return_pct": 0.3, "profit_factor": 1.2, "win_rate_pct": 55, "stop_hit_rate_pct": 40},
                {"threshold_pct": 70.0, "signals": 0, "coverage_pct": 0, "avg_trade_return_pct": None, "profit_factor": None, "win_rate_pct": None, "stop_hit_rate_pct": None},
            ]
        },
        {
            "threshold_report": [
                {"threshold_pct": 60.0, "signals": 8, "coverage_pct": 4, "avg_trade_return_pct": -0.1, "profit_factor": 0.9, "win_rate_pct": 45, "stop_hit_rate_pct": 55},
                {"threshold_pct": 70.0, "signals": 0, "coverage_pct": 0, "avg_trade_return_pct": None, "profit_factor": None, "win_rate_pct": None, "stop_hit_rate_pct": None},
            ]
        },
    ]
    summary = aggregate_threshold_summary(folds, [0.6, 0.7])
    by_threshold = {row["threshold_pct"]: row for row in summary}
    assert by_threshold[60.0]["total_signals"] == 18
    assert by_threshold[60.0]["positive_folds"] == 1
    assert by_threshold[70.0]["total_signals"] == 0
    assert by_threshold[70.0]["quality_label"] == "unstable"
