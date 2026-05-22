# ML v2 Trade PnL Model

ML v2 is a research layer for learning trade outcome quality, not just whether a fixed target is reached before a stop.

ML v1 predicts a target-before-stop style probability. Recent validation showed that adaptive target/stop improved hit structure, but candidate filters and composite rules did not find a durable edge. That suggests the model needs richer labels and PnL-aware evaluation.

## Labels

- `positive_trade_return`: `1` when realized trade return after costs is positive.
- `target_hit`: `1` when the simulated trade reaches target.
- `avoid_stop`: `1` when the simulated trade does not hit stop.
- `good_trade`: `1` when realized trade return is at least `0.5%`.
- `trade_return_pct`: diagnostic regression-like target included in the dataset output.

## Feature Groups

- Technical: returns, moving-average gaps, volatility, ATR, range position, distance to highs/lows, volume/value ratios.
- Volatility/liquidity: bucket encodings and log traded value.
- Market regime: historical regime encoding and available regime component scores.
- Trade setup: adaptive policy target, stop, RR and ATR multipliers.
- Sector/asset: stable numeric encodings for sector and asset type.
- News/global: not replayed as predictive historical features in v2 because reliable historical context is not available yet.

## No Leakage Principle

Features are built only from candles up to the current historical index. Future candles are used only to simulate the trade outcome and create labels.

Evaluation uses a time-based split: older samples train the model and newer samples test it. This avoids random leakage across adjacent dates.

## PnL-Aware Threshold Report

The threshold report selects test rows where predicted probability is above each threshold and reports:

- selected signal count and coverage;
- label hit rate;
- average trade return;
- profit factor;
- win rate;
- target-hit and stop-hit rates.

This is more useful than AUC alone because the model is meant to improve realized trade selection.

## Production Status

ML v2 does not replace ML v1 and is not used by consumer signal decision logic in this stage. It is a research/evaluation layer only. Any production use needs walk-forward validation and paper trading first.

## Limitations

- Labels are proxy outcomes from daily candles.
- MOEX historical data quality and survivorship bias can affect results.
- Daily candles do not provide full intraday target/stop ordering.
- Costs are simplified bps inputs.
- Historical news/global context is not replayed.
- The model can overfit and needs walk-forward validation.
- Not investment advice.

## Curl Examples

Dataset summary:

```bash
curl "http://127.0.0.1:8010/signals/ml-v2/dataset-summary?max_tickers=80&max_samples=3000&commission_bps=10&slippage_bps=5"
```

Evaluation:

```bash
curl "http://127.0.0.1:8010/signals/ml-v2/evaluation?max_tickers=80&max_samples=3000&label=positive_trade_return&commission_bps=10&slippage_bps=5"
```

Different label:

```bash
curl "http://127.0.0.1:8010/signals/ml-v2/evaluation?max_tickers=80&max_samples=3000&label=avoid_stop"
```
