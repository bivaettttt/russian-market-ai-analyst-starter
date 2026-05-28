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

If a consumer signal does not expose a usable position size, paper tracking uses `DEFAULT_PAPER_POSITION_SIZE_PCT = 1.0` as a fallback notional per row. The row and snapshot summary mark this as `position_size_source=fallback_default`. This fallback is for paper accounting only: it does not place trades and does not change consumer recommendations.

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

Lifecycle automation and CSV exports are documented in:

```text
docs/conservative_event_overlay_paper_tracking_lifecycle.md
```

Key lifecycle endpoints:

- `GET /signals/event-aware/conservative-overlay-paper-lifecycle-status`
- `GET /signals/event-aware/conservative-overlay-paper-ready`
- `POST /signals/event-aware/conservative-overlay-paper-evaluate-ready`
- `GET /signals/event-aware/conservative-overlay-paper-snapshots.csv`
- `GET /signals/event-aware/conservative-overlay-paper-dashboard.csv`

## Metrics

- `baseline_total_exposure`: sum of baseline paper position sizes.
- `overlay_total_exposure`: sum after conservative overlay multipliers.
- `default_paper_position_size_pct`: fallback notional used only when signal sizing is unavailable.
- `position_size_source`: `signal` or `fallback_default`.
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
- Legacy snapshots created before exposure accounting may have zero exposure; recreate official snapshots after the fix for meaningful baseline vs overlay PnL.
- No investment advice.
