from app.services.event_overlay_quality_report import (
    aggregate_quality_by_risk_level,
    aggregate_quality_cumulative_curve,
    build_data_health_warnings,
    classify_overlay_quality,
    recommend_quality_action,
)


def test_quality_label_classification():
    assert classify_overlay_quality(evaluated_items=0, overlay_delta_pnl_pct=None) == "insufficient_data"
    assert classify_overlay_quality(evaluated_items=20, overlay_delta_pnl_pct=0.2) == "improving"
    assert classify_overlay_quality(evaluated_items=20, overlay_delta_pnl_pct=-0.2) == "underperforming"
    assert classify_overlay_quality(evaluated_items=20, overlay_delta_pnl_pct=0.0) == "mixed"


def test_cumulative_curve_aggregation():
    rows = [
        {"snapshot_id": 2, "snapshot_date": "2026-01-02", "baseline_pnl_pct": 0.1, "overlay_pnl_pct": 0.2},
        {"snapshot_id": 1, "snapshot_date": "2026-01-01", "baseline_pnl_pct": -0.3, "overlay_pnl_pct": -0.1},
    ]

    curve = aggregate_quality_cumulative_curve(rows)

    assert curve[0]["snapshot_id"] == 1
    assert curve[-1]["baseline_cumulative_pnl_pct"] == -0.2
    assert curve[-1]["overlay_cumulative_pnl_pct"] == 0.1
    assert curve[-1]["delta_cumulative_pnl_pct"] == 0.3


def test_risk_level_aggregation():
    rows = [
        {
            "event_risk_level": "elevated",
            "baseline_realized_pnl_pct": -0.1,
            "overlay_realized_pnl_pct": -0.05,
            "overlay_delta_pnl_pct": 0.05,
            "realized_return_pct": -2.0,
            "event_risk_multiplier": 0.5,
        },
        {
            "event_risk_level": "elevated",
            "baseline_realized_pnl_pct": 0.2,
            "overlay_realized_pnl_pct": 0.1,
            "overlay_delta_pnl_pct": -0.1,
            "realized_return_pct": 3.0,
            "event_risk_multiplier": 0.5,
        },
    ]

    by_risk = aggregate_quality_by_risk_level(rows)

    assert by_risk[0]["risk_level"] == "elevated"
    assert by_risk[0]["items"] == 2
    assert by_risk[0]["delta_pnl_pct"] == -0.05
    assert by_risk[0]["win_rate_pct"] == 50.0


def test_quality_recommended_action():
    assert recommend_quality_action(snapshots_total=0, ready_to_evaluate=0, quality_label="insufficient_data") == "create_snapshot"
    assert recommend_quality_action(snapshots_total=3, ready_to_evaluate=2, quality_label="mixed") == "evaluate_ready"
    assert recommend_quality_action(snapshots_total=3, ready_to_evaluate=0, quality_label="underperforming") == "review_underperformance"


def test_data_health_warnings():
    warnings = build_data_health_warnings(
        {
            "last_market_candle_date": None,
            "total_snapshots": 0,
            "ready_snapshots": 0,
            "open_snapshots": 0,
            "event_count": 0,
        }
    )

    assert "stale_market_data" in warnings
    assert "no_snapshots" in warnings
    assert "event_coverage_missing" in warnings
