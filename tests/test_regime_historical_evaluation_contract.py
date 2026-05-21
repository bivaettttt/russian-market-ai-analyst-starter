from app.services.consumer_signal_backtest_audit import build_regime_historical_evaluation
from app.services.market_regime import build_market_regime_for_history_index


def _candles(start: float, step: float, count: int = 90):
    return [
        {
            "trade_date": f"2024-01-{(idx % 28) + 1:02d}",
            "open": start + step * idx,
            "high": start + step * idx + 1,
            "low": start + step * idx - 1,
            "close": start + step * idx,
            "volume": 1000,
        }
        for idx in range(count)
    ]


def test_historical_regime_contract_on_mock_candles():
    candles_by_ticker = {
        f"T{idx:02d}": _candles(100 + idx, 0.25)
        for idx in range(20)
    }
    index_by_ticker = {ticker: len(candles) - 1 for ticker, candles in candles_by_ticker.items()}

    result = build_market_regime_for_history_index(
        candles_by_ticker=candles_by_ticker,
        index_by_ticker=index_by_ticker,
        lookback=60,
        min_tickers=20,
    )

    assert result["ok"] is True
    assert result["regime"] in {"risk_on", "neutral", "risk_off"}
    assert "regime_score" in result
    assert "long_allowed" in result
    assert isinstance(result["reasons"], list)
    assert "avg_ret20_pct" in result["components"]


def test_regime_historical_evaluation_builder_is_callable():
    assert callable(build_regime_historical_evaluation)
