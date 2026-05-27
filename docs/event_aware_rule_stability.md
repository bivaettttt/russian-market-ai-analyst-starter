# Event-Aware Rule Stability Diagnostics

Static event-aware risk rules can look promising while failing in walk-forward. The usual causes are year/event concentration, regime dependence, missing too many winners, or unstable behavior across chronological buckets.

This diagnostic layer does not change production logic. It explains whether event-aware risk rules are stable enough to consider as a future risk overlay, or should remain diagnostic-only.

## Metrics

- by-year stability: rule behavior by calendar year;
- bucket stability: four chronological buckets independent of train/test selection;
- market regime breakdown: risk-on, neutral, risk-off, unknown;
- event family breakdown: rates, FX, sanctions, sector events and others;
- setup group breakdown: trend-like, rebound-like, quality-like;
- concentration: top ticker, event, year and sector shares;
- avoid benefit vs missed upside;
- failure modes.

## How To Read

- `stable_rules`: rules with enough samples, multi-year stability, low concentration and avoid benefit greater than missed upside.
- `moderate_rules`: interesting but not strong enough for a candidate overlay.
- `failure_analysis`: concise explanation of why static rules did not transfer.
- `recommended_use`: `stable_risk_filter`, `regime_specific_filter`, `diagnostic_only`, or `reject`.

## Outcomes

- `stable_risk_overlay_candidate`: at least one stable risk-filter rule exists.
- `diagnostic_only`: rules may help explanations but are not strong enough as filters.
- `reject_event_risk_filter`: event risk rules appear harmful or unstable.
- `needs_more_data`: insufficient samples/events.

## Next Steps

- If stable: build a simple risk overlay candidate and validate it leakage-safe.
- If diagnostic-only: keep event layer for explanations/risk annotations.
- If rejected: do not use event-aware rules as filters.

## Curl Examples

Quick:

```bash
curl "http://127.0.0.1:8010/signals/event-aware/rule-stability?max_tickers=20&max_samples=1000&max_events=1000&min_signals=5&max_rules=80"
```

Full:

```bash
curl "http://127.0.0.1:8010/signals/event-aware/rule-stability?max_tickers=80&max_samples=3000&max_events=10000&min_signals=20&max_rules=120"
```

## Limitations

- historical events include curated seed data;
- outcomes are proxy backtest labels;
- daily candle target/stop order is ambiguous;
- costs are simplified;
- no production signal logic changes;
- no investment advice.
