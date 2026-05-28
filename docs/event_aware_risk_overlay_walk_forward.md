# Event-Aware Risk Overlay Walk-forward

Static overlay backtest showed that soft exposure scaling can improve the risk-adjusted profile, but that is not enough. This validation checks the overlay leakage-safe: each fold calibrates overlay parameters on past samples and applies the selected config only to future samples.

## Static vs walk-forward

- Static overlay backtest applies one deterministic overlay to the whole historical sample.
- Walk-forward overlay validation chooses thresholds and multipliers on the train period only.
- Test metrics are calculated on future samples with the fixed train-selected config.

Production consumer signals remain unchanged by default.

## Config calibration

The bounded grid varies:

- risk-score thresholds for moderate/elevated/high/extreme;
- position multipliers for each risk level;
- winner-miss penalty used to make the overlay less aggressive when rules have missed-winner risk.

If every train config is harmful, the fold selects `disabled`, which is equivalent to full baseline exposure.

## Metrics

- `weighted_return_delta_pct`: overlay weighted average return minus full-exposure baseline.
- `weighted_profit_factor_delta`: weighted PF minus baseline PF.
- `stop_hit_exposure_delta_pct`: weighted stop-hit exposure minus baseline stop-hit rate.
- `exposure_reduction_pct`: average reduction in exposure from position multipliers.
- `avg_position_multiplier`: average retained exposure.
- `positive_return_delta_folds` / `positive_pf_delta_folds`: stability across folds.

## Recommendations

- `promising_soft_overlay`: most folds improve return and PF, average deltas are positive, and exposure is not cut too aggressively.
- `research_only`: partial improvement, but not stable enough for production default.
- `reject`: no stable improvement.
- `needs_more_data`: too few event samples or folds.

## Examples

```bash
curl "http://127.0.0.1:8010/signals/event-aware/risk-overlay-walk-forward?max_tickers=20&max_samples=1000&max_events=1000&folds=3&min_train_samples=30&min_test_samples=15&max_configs=20"

curl "http://127.0.0.1:8010/signals/event-aware/risk-overlay-walk-forward?max_tickers=80&max_samples=3000&max_events=10000&folds=4&min_train_samples=100&min_test_samples=50&max_configs=60&commission_bps=10&slippage_bps=5"

curl "http://127.0.0.1:8010/signals/event-aware/risk-overlay-walk-forward?max_tickers=80&max_samples=3000&max_events=10000&max_configs=20"
```

## Limitations

- Historical events are curated research data.
- Proxy backtest labels use daily candles and simplified execution assumptions.
- The endpoint validates exposure weighting, not a production action change.
- Overlay remains opt-in and requires paper trading before default use.
- No investment advice.
