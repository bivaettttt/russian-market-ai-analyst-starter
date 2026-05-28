# Conservative Event Overlay Paper Tracking

Conservative event overlay calibration produced the first practical event-aware risk-layer candidate, but calibration and current snapshots are still research outputs. Paper tracking stores opt-in conservative overlay snapshots locally and evaluates them later against newly available MOEX candles.

This layer does not change production consumer recommendations, does not place trades, and is not investment advice.

## Snapshot vs Tracking

- `/signals/event-aware/conservative-overlay-paper-snapshot` is read-only current comparison: baseline exposure vs conservative overlay exposure.
- Paper tracking writes a local snapshot, keeps item-level signal/risk/position data, and later evaluates realized outcomes.

## Create Snapshot

```bash
curl -X POST \
  "http://127.0.0.1:8010/signals/event-aware/conservative-overlay-paper-snapshots?name=daily-paper&limit=100&horizon_days=20"
```

Stored fields include baseline position size, overlay-adjusted size, entry price/date, event risk score/level/reasons, matched rules, and config id.

## List, Detail, Evaluate

```bash
curl "http://127.0.0.1:8010/signals/event-aware/conservative-overlay-paper-snapshots?limit=20"

curl "http://127.0.0.1:8010/signals/event-aware/conservative-overlay-paper-snapshots/1"

curl -X POST \
  "http://127.0.0.1:8010/signals/event-aware/conservative-overlay-paper-snapshots/1/evaluate"

curl "http://127.0.0.1:8010/signals/event-aware/conservative-overlay-paper-dashboard?limit=20"
```

The tracking page is available at:

```text
/signals/event-aware/conservative-overlay-paper-tracking-page
```

## Metrics

- `baseline_total_exposure`: sum of baseline paper position sizes.
- `overlay_total_exposure`: sum after conservative overlay multipliers.
- `realized_return_pct`: close-to-close ticker return from entry to evaluation candle.
- `baseline_realized_pnl_pct`: `realized_return_pct * base_position_size_pct / 100`.
- `overlay_realized_pnl_pct`: `realized_return_pct * overlay_position_size_pct / 100`.
- `overlay_delta_pnl_pct`: overlay PnL minus baseline PnL.
- `by_risk_level`: realized contribution grouped by event risk level.

## Recommended Routine

1. Create a snapshot daily or weekly.
2. Evaluate after the configured horizon, for example 20 calendar days.
3. Compare baseline vs overlay across risk levels and market regimes.
4. Track at least 2-3 months before any product decision.

## Limitations

- Paper trading only.
- No real execution, order book, latency, or liquidity model.
- Evaluation uses available local candles and close-to-close proxy logic.
- Historical event data is curated research data.
- No investment advice.
