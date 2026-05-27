# Setup Family Research

Setup family research exists because ML v3, trained directly on consumer candidates, still did not find a stable edge. That points to weak candidate generation rather than weak post-filtering. This layer tests transparent long setup families before changing any production rules.

The endpoint `/signals/setup-family/research` classifies historical candle-only samples into setup families without using future candles. Future candles are used only for target/stop outcome simulation.

## Setup Families

- `breakout`: close near 20/60-day highs, above SMA20, positive 5-day return, volume confirmation.
- `pullback`: broader uptrend with short-term flat/negative return near SMA support.
- `mean_reversion`: close near recent lows after short-term weakness, without crash-like volatility.
- `momentum_continuation`: positive 5/20-day momentum above moving averages.
- `volatility_squeeze`: low volatility and compressed range with close in upper half.
- `trend_following`: close above aligned SMA20/SMA50 with positive 20-day return.
- `blue_chip_liquidity`: high traded value and non-extreme volatility.
- `low_volatility_quality`: low/medium volatility, enough liquidity, no large selloff.
- `oversold_rebound`: oversold short-term move with last-candle bounce.
- `regime_supported_long`: market regime not risk-off when regime context is available.

## Reading Results

- `profit_factor`: gross wins divided by gross losses for simulated trades.
- `avg_trade_return_pct`: average realized target/stop/timeout return after simplified costs.
- `stop_hit_rate_pct`: share of samples hitting stop first.
- `quality_label`: `good`, `medium`, `weak`, `bad`, or `unstable`.
- `parameter sweep`: bounded threshold grid for setup definitions; it is not optimizer output ready for production.

## Endpoints

Quick research:

```bash
curl "http://127.0.0.1:8010/signals/setup-family/research?max_tickers=20&max_samples=1000&min_signals=10"
```

Full research:

```bash
curl "http://127.0.0.1:8010/signals/setup-family/research?max_tickers=80&max_samples=3000&min_signals=30&commission_bps=10&slippage_bps=5"
```

Sweep one family:

```bash
curl "http://127.0.0.1:8010/signals/setup-family/sweep?setup_family=breakout&max_tickers=80&max_samples=3000&max_configs=20&min_signals=30"
```

## Limitations

- Setup definitions are heuristic.
- Backtest is proxy historical research, not production replay.
- Daily candles cannot fully resolve intraday target/stop order.
- Costs are simplified.
- Local universe can contain survivorship and coverage bias.
- Any promising setup requires walk-forward and paper trading validation.

No production consumer logic is changed by this research layer.
