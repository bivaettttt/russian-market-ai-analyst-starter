# Event-Aware Walk-Forward Validation

Event-aware research found high-PF combinations after historical event bootstrap, but a combo like `regime_supported_long+sector_news_negative` with PF above 5 on 37 samples can easily be overfit to one event window, year, ticker group or sector.

The first full walk-forward run after the initial seed showed positive average selected PF but only `1/4` positive folds. That means the static event-aware edge was not stable enough; seed v2 expands historical event coverage so fold-level coverage is easier to diagnose.

If detailed combo selection remains too sparse, use Event-Aware Generalized Rule Search to test broader rules such as event groups, setup groups, confirmation/conflict buckets and event-score thresholds.

Walk-forward validation checks whether the edge survives a leakage-safe process:

1. Build historical setup + event samples.
2. Sort by date.
3. For each fold, select event/setup combinations using only the train period.
4. Apply those selected combinations only to the future test period.
5. Compare selected test trades with broad event-aware baseline, confirmed-only and setup-only buckets.

## Baselines

- all event-aware test samples;
- setup-only test samples;
- confirmed-only test samples;
- selected train-combos applied to future test samples.

## How To Read

- `positive_folds`: number of folds where selected test samples had positive average return.
- `avg_test_selected_profit_factor`: average PF of selected future samples across completed folds.
- `avg_delta_vs_baseline_return_pct`: selected future avg return minus broad event-aware test baseline.
- `selected_combo_frequency`: how often a combo was selected from train and how it performed in test.
- `fold_event_coverage`: train/test event and confirmed sample counts by fold and year.
- `event_samples_by_year` / `confirmed_samples_by_year`: whether the event layer is distributed across the historical period.
- `concentration`: top ticker/event/year share in selected test rows.
- `recommendation`: `promising_event_edge`, `research_only`, `reject`, or `needs_more_event_data`.

## Criteria For A Future Experimental Generator

- average selected PF at least `1.10`;
- average selected return above `0`;
- at least `3/4` positive folds in a four-fold run;
- no extreme concentration in one ticker, event or year;
- then validate with paper trading before production integration.

## Curl Examples

Quick:

```bash
curl "http://127.0.0.1:8010/signals/event-aware/walk-forward?max_tickers=20&max_samples=1000&max_events=1000&folds=3&min_train_samples=30&min_test_samples=15&min_signals=3&top_k_combos=3"
```

Full:

```bash
curl "http://127.0.0.1:8010/signals/event-aware/walk-forward?max_tickers=80&max_samples=3000&max_events=10000&folds=4&min_train_samples=100&min_test_samples=50&min_signals=10&top_k_combos=5"
```

Lower signal threshold:

```bash
curl "http://127.0.0.1:8010/signals/event-aware/walk-forward?max_tickers=80&max_samples=3000&max_events=10000&folds=4&min_signals=5"
```

Top-k variation:

```bash
curl "http://127.0.0.1:8010/signals/event-aware/walk-forward?max_tickers=80&max_samples=3000&max_events=10000&top_k_combos=10"
```

## Limitations

- historical event data includes curated seed events;
- event timestamps are daily;
- proxy backtest uses daily candles and simplified target/stop ordering;
- costs are simplified;
- this does not change production consumer logic.
