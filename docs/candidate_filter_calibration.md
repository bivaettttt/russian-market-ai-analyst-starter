# Candidate Filter Calibration

Candidate filter calibration checks whether simple research filters improve proxy trade PnL after expectancy breakdown has identified positive and negative pockets.

It does not apply filters to production signals automatically.

## Difference From Expectancy Breakdown

Expectancy breakdown shows where the model wins or loses by bucket: ticker, regime, volatility, liquidity, probability, RR and audit dimensions.

Candidate filter calibration tests whether excluding negative pockets or including positive pockets improves the full sample metrics while preserving reasonable coverage.

## Filters Tested

- Single exclude filters for negative buckets.
- Single include-only filters for positive buckets.
- Group filters: exclude top 5/10/15 negative tickers.
- Group filters: include only top 5/10/15 positive tickers.
- Simple combo filters:
  - exclude `risk_off` plus low probability;
  - exclude high/extreme volatility plus low liquidity.

## How To Read Metrics

- `avg_trade_return_delta_pct`: filtered avg trade return minus baseline.
- `profit_factor_delta`: filtered profit factor minus baseline.
- `coverage_after_filter_pct`: percentage of samples kept after filtering.
- `avoided_losses`: losing trades removed by the filter.
- `missed_wins`: winning trades removed by the filter.
- `score`: ranking score balancing return, profit factor, win rate, stop-hit improvement, losses avoided, missed wins and coverage.
- `quality_label`: `good`, `medium`, `weak` or `unstable`.

## Why Filters Are Not Applied Automatically

Good-looking filters can overfit the current sample, destroy future coverage, or rely on noisy buckets. Any promising filter should go through walk-forward validation and paper trading before production use.

## Limitations

- Proxy historical data, not full live endpoint replay.
- Small sample risk in narrow pockets.
- Overfitting risk when many filters are tried.
- Simplified commission/slippage costs.
- Daily candles do not provide intraday target/stop order.
- Current instrument universe can introduce survivorship bias.

## Curl Examples

Quick:

```bash
curl "http://127.0.0.1:8010/signals/consumer/candidate-filter-calibration?max_tickers=10&max_samples=300&max_filters=30"
```

With fixed policy:

```bash
curl "http://127.0.0.1:8010/signals/consumer/candidate-filter-calibration?max_tickers=50&max_samples=1500&use_best_adaptive_policy=false"
```

With best adaptive policy and costs:

```bash
curl "http://127.0.0.1:8010/signals/consumer/candidate-filter-calibration?max_tickers=80&max_samples=3000&max_filters=80&commission_bps=10&slippage_bps=5&use_best_adaptive_policy=true"
```
