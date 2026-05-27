# Dual-Side Event-Aware Outcome Research

Long-only event-aware rules were rejected in walk-forward validation: generalized rules selected enough samples, but average selected PF stayed below `1` and positive folds remained weak. This suggests events may be more useful as risk context than as long-entry triggers.

This layer studies event-aware samples as:

- long candidate: a rule may support a long trade;
- avoid-long: a rule may identify trades better skipped;
- downside watch: a rule may warn about negative return or stop-hit risk;
- risk filter: a rule may reduce exposure by blocking weak long candidates.

It does not create production short recommendations and does not change production consumer logic.

## Outcomes

Each event/setup sample is enriched with:

- `long_trade_return_pct`;
- `long_outcome`;
- `long_stop_hit_flag`;
- `long_target_hit_flag`;
- `future_return_pct`;
- `future_min_return_pct`;
- `future_max_return_pct`;
- `negative_return_flag`;
- `downside_flag`;
- `severe_downside_flag`;
- `avoid_long_benefit_pct`;
- `missed_upside_pct`;
- `risk_adjusted_avoid_score`.

When full future path fields are unavailable, the layer uses available proxy fields such as trade return, outcome, MAE and MFE.

## Static Research

Static research ranks generalized event-aware rules by downside/risk predictive value:

- best avoid-long rules;
- best downside-watch rules;
- best long-candidate rules if any.

Avoid-long quality improves when a rule has enough samples, negative long return, elevated stop-hit/negative-return rates and avoided loss greater than missed upside.

## Walk-Forward Risk Filter

Walk-forward validation avoids leakage:

1. Train folds rank avoid-long/downside rules using past samples only.
2. Test folds apply selected rules as a risk filter.
3. Matching trades are blocked/avoided.
4. Remaining kept trades are compared with baseline test event trades.

Key fields:

- `avg_return_delta_pct`;
- `profit_factor_delta`;
- `stop_hit_delta_pct`;
- `coverage_after_filter_pct`;
- `avoided_losses`;
- `missed_winners`;
- `avoided_loss_return_pct`;
- `missed_upside_pct`.

## Success Criteria

Future risk-layer integration requires:

- positive impact folds at least `3/4`;
- average return delta above `0`;
- PF delta above `0`;
- stop-hit delta below `0`;
- coverage after filter above `50%`;
- no production action named as a short recommendation.

## Curl Examples

Static:

```bash
curl "http://127.0.0.1:8010/signals/event-aware/dual-side-research?max_tickers=80&max_samples=3000&max_events=10000&min_signals=20&max_rules=120"
```

Walk-forward:

```bash
curl "http://127.0.0.1:8010/signals/event-aware/dual-side-walk-forward?max_tickers=80&max_samples=3000&max_events=10000&folds=4&min_train_samples=100&min_test_samples=50&min_signals=20&max_rules=120&top_k_rules=5"
```

Quick:

```bash
curl "http://127.0.0.1:8010/signals/event-aware/dual-side-walk-forward?max_tickers=20&max_samples=1000&max_events=1000&folds=3&min_signals=5"
```

## Limitations

- event history includes curated seed data;
- proxy backtest uses daily candles;
- daily target/stop ordering is ambiguous;
- risk outcomes are research labels, not production decisions;
- no investment advice.
