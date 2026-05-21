from app.services.expectancy_breakdown import build_bucket_row, build_expectancy_breakdown


def test_expectancy_breakdown_builder_is_callable():
    assert callable(build_expectancy_breakdown)


def test_build_bucket_row_labels_positive_negative_unstable():
    positive = build_bucket_row(
        dimension="market_regime",
        bucket="risk_on",
        raw_bucket={
            "samples": 20,
            "target_hits": 12,
            "stop_hits": 6,
            "timeouts": 2,
            "forward_returns": [1.0] * 20,
            "mfe_values": [3.0] * 20,
            "mae_values": [-1.0] * 20,
            "trade_rows": [{"outcome": "target_hit", "trade_return_pct": 5}] * 12
            + [{"outcome": "stop_hit", "trade_return_pct": -3}] * 6
            + [{"outcome": "timeout", "trade_return_pct": 1}] * 2,
        },
        total_samples=40,
        min_bucket_samples=20,
    )
    negative = build_bucket_row(
        dimension="market_regime",
        bucket="risk_off",
        raw_bucket={
            "samples": 20,
            "target_hits": 5,
            "stop_hits": 12,
            "timeouts": 3,
            "forward_returns": [-1.0] * 20,
            "mfe_values": [2.0] * 20,
            "mae_values": [-3.0] * 20,
            "trade_rows": [{"outcome": "target_hit", "trade_return_pct": 5}] * 5
            + [{"outcome": "stop_hit", "trade_return_pct": -3}] * 12
            + [{"outcome": "timeout", "trade_return_pct": -1}] * 3,
        },
        total_samples=40,
        min_bucket_samples=20,
    )
    unstable = build_bucket_row(
        dimension="sector",
        bucket="unknown",
        raw_bucket={
            "samples": 3,
            "target_hits": 2,
            "stop_hits": 1,
            "timeouts": 0,
            "forward_returns": [1.0, 2.0, -1.0],
            "mfe_values": [3.0, 4.0, 1.0],
            "mae_values": [-1.0, -1.0, -2.0],
            "trade_rows": [
                {"outcome": "target_hit", "trade_return_pct": 5},
                {"outcome": "target_hit", "trade_return_pct": 5},
                {"outcome": "stop_hit", "trade_return_pct": -3},
            ],
        },
        total_samples=40,
        min_bucket_samples=20,
    )

    assert positive["quality_label"] == "positive"
    assert negative["quality_label"] == "negative"
    assert unstable["quality_label"] == "unstable"
    assert positive["coverage_pct"] == 50.0
    assert "diagnostic" in positive
