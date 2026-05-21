# Market Regime Filter

`market_regime` is an explainable market-wide filter for consumer signals. It does not replace ticker technicals, ML, risk, news, global macro events, or `signal_audit`; it adds a market context gate on top of them.

## Regimes

- `risk_on`: market breadth and 20-day trend support long scenarios.
- `neutral`: no strong market-wide edge.
- `risk_off`: downside pressure and/or volatility are high enough that long signals need stricter confirmation.

The live endpoint is:

```bash
curl "http://127.0.0.1:8000/signals/market-regime"
```

Important fields:

- `regime`, `regime_score`
- `trend_score`, `breadth_score`
- `volatility_score`, `downside_pressure`
- `long_allowed`
- `position_multiplier`
- `min_rr_multiplier`
- `min_ml_probability_addon`
- `reasons`, `warnings`

If market data is insufficient, the service returns `neutral`, `long_allowed=true`, `position_multiplier=0.75`, and warning `insufficient_market_regime_data`.

## Calculation

The current implementation uses local candle data only:

- share of eligible tickers above SMA20;
- share with positive 5d and 20d returns;
- share with 20d return below -5%;
- share near 20d lows;
- negative momentum share;
- average realized 20d daily volatility.

The score is an explainable weighted proxy:

```text
regime_score = trend_score * 0.35
             + breadth_score * 0.35
             - downside_pressure * 0.20
             - volatility_score * 0.10
```

## Effect On Consumer Signals

Forecast fields added:

- `market_regime`
- `market_regime_adjustment_pct`
- `market_regime_gate`
- `market_regime_reason`
- `market_regime_position_multiplier`
- `market_regime_min_rr_multiplier`
- `market_regime_min_ml_probability_addon`
- `effective_min_rr`
- `effective_min_ml_probability`

In `risk_off`, long signals can be downgraded to `watch_market_risk` or `avoid_market_risk` when `long_allowed=false`. Position sizing is multiplied by `position_multiplier`; if the multiplier is zero, the position is blocked. `signal_audit.layer_scores.market_regime` explains this and can add `market_regime_risk_off` to `blocked_by`.

`risk_on` gives only a small probability support. `neutral` mainly records diagnostics.

## Why It Was Added

Walk-forward validation rejected the current threshold set because test score decayed and stop-hit rate stayed high. The next conservative step is not to loosen thresholds, but to add a market-wide regime filter so long entries are reduced during broad risk-off conditions.

## Checks

```bash
curl "http://127.0.0.1:8000/signals/market-regime"
curl "http://127.0.0.1:8000/signals/consumer/SBER.json"
curl "http://127.0.0.1:8000/signals/consumer.json?scenario=long"
curl "http://127.0.0.1:8000/signals/consumer/backtest-audit?max_tickers=10&max_samples=200&use_market_regime_filter=true"
curl "http://127.0.0.1:8000/signals/consumer/threshold-sweep?max_tickers=10&max_samples=200&max_configs=40&use_market_regime_filter=true"
curl "http://127.0.0.1:8000/signals/consumer/walk-forward?max_tickers=10&max_samples=300&max_configs=40&folds=2&use_market_regime_filter=true"
```

## Limitations

- Market breadth is calculated on the current local eligible universe.
- If index candles such as IMOEX are unavailable, the filter uses breadth proxies.
- Historical regime in backtest/sweep/walk-forward is an approximation from daily candles.
- No commissions, slippage, tax, or intraday order are modeled.
- This is an evaluation and risk-control layer, not an investment recommendation.
