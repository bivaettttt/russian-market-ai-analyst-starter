# Conservative Event Risk Overlay Calibration

The first event risk overlay walk-forward improved the risk-adjusted profile, but it was too aggressive:

- avg return delta: `+0.28%`;
- avg PF delta: `+0.199`;
- stop-hit exposure delta: `-4.825 pp`;
- exposure reduction: `70.73%`;
- avg position multiplier: `0.293`.

This calibration searches for a softer overlay that preserves PF and stop-hit improvements while keeping exposure usable.

## Objective

Target constraints:

- avg position multiplier `>= 0.50`;
- exposure reduction `<= 50%`;
- positive PF folds `>= 3/4`;
- stop-hit exposure improves;
- positive return folds ideally `>= 2/4`.

The endpoint is research-only and does not change production consumer behavior.

## Config Grid

The conservative grid uses higher risk-score thresholds and milder multipliers:

- moderate threshold: `20/25/30`;
- elevated threshold: `40/45/50`;
- high threshold: `60/65/70`;
- extreme threshold: `80/85`;
- moderate multiplier: `0.95/0.90/0.85`;
- elevated multiplier: `0.80/0.75/0.70`;
- high multiplier: `0.65/0.60/0.55`;
- extreme multiplier: `0.50/0.40`;
- winner-miss penalty: `0.5/0.75/1.0`.

The search also includes `disabled`, the previous aggressive benchmark, and the default soft overlay benchmark.

## Metrics

- `conservative_score`: balanced score that rewards PF/return/stop-hit improvement and penalizes excessive exposure cuts.
- `weighted_return_delta_pct`: overlay weighted return minus baseline full exposure.
- `weighted_profit_factor_delta`: weighted PF minus baseline PF.
- `stop_hit_exposure_delta_pct`: weighted stop-hit exposure minus baseline stop-hit rate.
- `exposure_reduction_pct`: average exposure cut.
- `avg_position_multiplier`: retained average exposure.

## Recommendations

- `conservative_overlay_candidate`: constraints pass, PF folds are stable, stop-hit improves, and at least two return folds are positive.
- `research_only`: some improvements exist, but constraints or stability are not strong enough.
- `reject`: no conservative config improves the profile.
- `needs_more_data`: too few samples or folds.

## Examples

```bash
curl "http://127.0.0.1:8010/signals/event-aware/risk-overlay-conservative-calibration?max_tickers=20&max_samples=1000&max_events=1000&folds=3&min_train_samples=30&min_test_samples=15&max_configs=30"

curl "http://127.0.0.1:8010/signals/event-aware/risk-overlay-conservative-calibration?max_tickers=80&max_samples=3000&max_events=10000&folds=4&min_train_samples=100&min_test_samples=50&max_configs=100&min_avg_position_multiplier=0.5&max_exposure_reduction_pct=50&min_positive_pf_folds=3"
```

## Limitations

- Still a research validation layer.
- No production default change.
- Historical events are curated and proxy labels use daily candles.
- Paper trading is required before using a calibrated overlay as a default risk control.
- No investment advice.
