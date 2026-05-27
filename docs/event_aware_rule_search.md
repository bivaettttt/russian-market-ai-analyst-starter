# Event-Aware Generalized Rule Search

Narrow event-aware walk-forward selected very few future samples (`5/0/0/2` by fold). The issue is that detailed keys like `setup_family + event_family + direction + confirmation` can look excellent in static research but remain too sparse out of sample.

This layer searches broader event-aware rules that can select more trades per fold while still avoiding leakage.

## Rule Families

- confirmation: positive confirmed events with any/trend/rebound setups;
- conflict/rebound: negative event conflicts treated as possible rebound candidates;
- event group: macro/rates, risk/FX, commodity, corporate, sector;
- setup group + event direction: trend-like, rebound-like and quality-like setups by event direction;
- event score threshold: absolute event score and setup score thresholds;
- broad coverage: any setup with event, non-negative event, event-only positive;
- filter style: confirmed/neutral only, exclude geopolitical/sanctions negatives, exclude low-score events.

## Matching

Rules are deterministic dictionaries with `conditions` and supported operations:

- `==`, `!=`;
- `in`, `not_in`;
- `>=`, `>`, `<=`, `<`;
- `exists`, `not_exists`.

Samples are enriched with derived fields such as `setup_group`, `event_group`, `is_conflict`, `is_confirmed`, `is_high_event_score`, `conflict_rebound_candidate` and `positive_confirmation_candidate`.

## Walk-Forward

1. Build event-aware samples from historical candles and local events.
2. Sort event samples by date.
3. On each fold, evaluate and rank rules using train samples only.
4. Select top train rules.
5. Apply selected rules to future test samples.
6. Union selected test rows so the same ticker/date/setup/event sample is not double-counted.

## How To Read

- `static_best_rules`: best rules over the full research sample; useful for diagnostics, not enough for adoption.
- `folds`: train-selected rules and future test metrics.
- `rule_frequency`: how often a rule was selected and its average future performance.
- `avg_selected_samples_per_fold`: whether the generalized rule has enough out-of-sample coverage.
- `concentration`: top ticker/event/year share in selected test rows.
- `recommendation`: `promising_generalized_event_rule`, `research_only`, `reject`, or `needs_more_data`.

## Candidate Generator Criteria

Before building Event-Aware Candidate Generator v1, require:

- positive folds at least `3/4`;
- selected PF at least `1.10`;
- selected average return above `0`;
- average selected samples per fold at least `min_signals`;
- no extreme concentration in one ticker, event or year.

## Curl Examples

Quick:

```bash
curl "http://127.0.0.1:8010/signals/event-aware/rule-search?max_tickers=20&max_samples=1000&max_events=1000&folds=3&min_train_samples=30&min_test_samples=15&min_signals=5&max_rules=80&top_k_rules=5"
```

Full:

```bash
curl "http://127.0.0.1:8010/signals/event-aware/rule-search?max_tickers=80&max_samples=3000&max_events=10000&folds=4&min_train_samples=100&min_test_samples=50&min_signals=20&max_rules=120&top_k_rules=5"
```

Low `min_signals`:

```bash
curl "http://127.0.0.1:8010/signals/event-aware/rule-search?max_tickers=80&max_samples=3000&max_events=10000&min_signals=10"
```

Larger top-k:

```bash
curl "http://127.0.0.1:8010/signals/event-aware/rule-search?max_tickers=80&max_samples=3000&max_events=10000&top_k_rules=10"
```

## Limitations

- event history includes curated seed data;
- rule search can still overfit the seed distribution;
- proxy backtest uses daily candles and simplified costs;
- daily target/stop ordering is ambiguous;
- this is research-only and does not change production logic.

## Next Step

If long-only generalized rules are rejected, use Dual-Side Event-Aware Outcome Research to test whether the same event context works better as an avoid-long, downside-watch or reduce-exposure risk filter.
