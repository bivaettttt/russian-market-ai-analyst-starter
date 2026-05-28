# Event-Aware Risk Overlay v1

Event-aware hard filters found risk, but leakage-safe walk-forward rejected them: avoided losses and missed winners were nearly balanced. The overlay therefore does not block a trade by default. It converts event-aware risk into softer controls:

- lower diagnostic position size;
- higher minimum probability requirement;
- higher minimum RR requirement;
- risk warnings and audit layer notes;
- action downgrade only in explicit experimental mode.

## Modes

- `diagnostic_only`: calculate score and fields, do not change action or size.
- `soft_adjust`: keep action unchanged, add effective position/probability/RR adjustments.
- `experimental_downgrade`: for high/extreme risk only, long-positive actions can become `watch_event_risk`.

Default production behavior is unchanged unless `use_event_risk_overlay=true` is passed.

## Fields

- `event_risk_score`
- `event_risk_level`
- `event_risk_position_multiplier`
- `event_risk_min_probability_addon_pct`
- `event_risk_min_rr_multiplier`
- `event_risk_effective_min_probability_pct`
- `event_risk_effective_min_rr`
- `event_risk_matched_rule_ids`
- `event_risk_reasons`
- `event_risk_action_effect`

## Examples

```bash
curl "http://127.0.0.1:8010/signals/consumer/SBER.json?use_event_risk_overlay=true"
curl "http://127.0.0.1:8010/signals/consumer.json?limit=50&use_event_risk_overlay=true&event_risk_overlay_mode=soft_adjust"
curl "http://127.0.0.1:8010/signals/consumer/event-risk-overlay-compare?limit=50&event_risk_overlay_mode=soft_adjust"
curl "http://127.0.0.1:8010/signals/event-aware/risk-overlay-backtest?max_tickers=80&max_samples=3000&max_events=10000"
curl "http://127.0.0.1:8010/signals/event-aware/risk-overlay-walk-forward?max_tickers=80&max_samples=3000&max_events=10000&folds=4&max_configs=60"
```

## Walk-forward validation

Use `/signals/event-aware/risk-overlay-walk-forward` to validate the overlay leakage-safe. Each fold selects thresholds and multipliers on the train period, then applies only that selected config to future test samples.

Read [event_aware_risk_overlay_walk_forward.md](event_aware_risk_overlay_walk_forward.md) for the metric definitions and recommendation criteria.

## Limitations

- Research-only overlay; not production default.
- Deterministic rule scoring from event-aware stability diagnostics.
- Hard filtering failed because of `winner_miss_rate`.
- Static backtest is exposure-weighted diagnostics; walk-forward validation is still research-only.
- Needs paper trading and no investment advice.
