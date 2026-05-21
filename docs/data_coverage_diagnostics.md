# Data Coverage Diagnostics

Data coverage diagnostics explains whether the local database has enough instruments and candles to build historical samples for backtest audit, adaptive calibration, walk-forward validation and expectancy breakdown.

This is a diagnostic/data quality layer. It does not change signal logic, thresholds, risk rules, position sizing or model decisions.

## Why Historical Samples Can Be Zero

Research endpoints need eligible instruments with supported `asset_type` and enough valid OHLC candles. A ticker is usable only when it has at least:

`min_history + horizon + 1`

valid candles.

For the default `min_history=80` and `horizon=20`, a ticker needs at least 101 valid OHLC rows. If no candidate ticker passes that threshold, endpoints such as expectancy breakdown can return `samples=0`.

## Important Parameters

- `max_tickers`: how many instruments to inspect in ticker order.
- `min_history`: minimum historical candles required before a sample can be formed.
- `horizon`: forward candles required to evaluate target/stop/timeout.
- `candles_limit`: output limit for ticker tables/examples.

## How To Read The Report

- `usable_tickers`: candidate tickers that have supported mapping and enough valid OHLC candles.
- `total_possible_samples`: approximate maximum samples from usable tickers for the selected `min_history/horizon`.
- `skip_reasons`: why inspected tickers do not produce samples.
- `main_blocker`: largest skip reason excluding `ok`.
- `coverage_level`:
  - `empty`: no possible samples.
  - `weak`: fewer than 500 possible samples or fewer than 10 usable tickers.
  - `medium`: fewer than 5000 possible samples or fewer than 50 usable tickers.
  - `good`: enough coverage for broader diagnostics.

## What To Do By Skip Reason

- `no_candles`: load candles for eligible tickers.
- `too_few_candles`: load a longer history or lower `min_history` for diagnostics.
- `insufficient_horizon`: load more recent/forward candles or reduce `horizon`.
- `invalid_ohlc`: inspect the candle import pipeline for missing open/high/low/close values.
- `unsupported_asset_type`: check whether `asset_type` should be normalized to `stock`, `share`, `equity` or `unknown`.
- `not_signal_eligible`: check whether `is_signal_eligible` is correctly set for the intended signal universe.

## Curl Examples

Quick:

```bash
curl "http://127.0.0.1:8010/signals/data-coverage?max_tickers=100&min_history=80&horizon=20"
```

Lower `min_history`:

```bash
curl "http://127.0.0.1:8010/signals/data-coverage?max_tickers=100&min_history=40&horizon=20"
```

Larger universe:

```bash
curl "http://127.0.0.1:8010/signals/data-coverage?max_tickers=1000&min_history=80&horizon=20"
```

HTML page:

```bash
open "http://127.0.0.1:8010/signals/data-coverage-page"
```

## Related Research Endpoints

- Expectancy breakdown depends on usable historical samples to split trade PnL by segment.
- Adaptive calibration depends on enough history to compare target/stop policies.
- Backtest audit depends on enough valid candles to build proxy historical consumer signals.

If any of those endpoints returns `samples=0`, run data coverage diagnostics first.
