from app.services.adaptive_trade_calibration import aggregate_trade_pnl_metrics, simulate_trade_outcome


def test_simulate_trade_target_hit():
    result = simulate_trade_outcome(
        entry_price=100,
        target_price=105,
        stop_price=97,
        future_candles=[{"high": 106, "low": 100, "close": 104}],
    )

    assert result["outcome"] == "target_hit"
    assert result["trade_return_pct"] == 5.0
    assert result["target_return_pct"] == 5.0


def test_simulate_trade_stop_hit():
    result = simulate_trade_outcome(
        entry_price=100,
        target_price=105,
        stop_price=97,
        future_candles=[{"high": 101, "low": 96, "close": 98}],
    )

    assert result["outcome"] == "stop_hit"
    assert result["trade_return_pct"] == -3.0


def test_simulate_trade_same_candle_conflict_is_conservative():
    result = simulate_trade_outcome(
        entry_price=100,
        target_price=105,
        stop_price=97,
        future_candles=[{"high": 106, "low": 96, "close": 101}],
        conservative_same_candle=True,
    )

    assert result["outcome"] == "stop_hit"
    assert result["same_candle_conflict"] is True


def test_simulate_trade_timeout_uses_forward_return():
    result = simulate_trade_outcome(
        entry_price=100,
        target_price=105,
        stop_price=97,
        future_candles=[{"high": 104, "low": 98, "close": 102}],
    )

    assert result["outcome"] == "timeout"
    assert result["trade_return_pct"] == 2.0


def test_simulate_trade_costs_reduce_return():
    result = simulate_trade_outcome(
        entry_price=100,
        target_price=105,
        stop_price=97,
        future_candles=[{"high": 106, "low": 100, "close": 104}],
        commission_bps=10,
        slippage_bps=5,
    )

    assert result["cost_pct"] == 0.15
    assert result["trade_return_pct"] == 4.85


def test_aggregate_trade_pnl_metrics():
    metrics = aggregate_trade_pnl_metrics(
        [
            {"outcome": "target_hit", "trade_return_pct": 5},
            {"outcome": "stop_hit", "trade_return_pct": -3},
            {"outcome": "timeout", "trade_return_pct": 2},
        ]
    )

    assert metrics["trades"] == 3
    assert metrics["wins"] == 2
    assert metrics["losses"] == 1
    assert metrics["win_rate_pct"] == 66.67
    assert metrics["profit_factor"] == 2.333
    assert metrics["payoff_ratio"] == 1.167
