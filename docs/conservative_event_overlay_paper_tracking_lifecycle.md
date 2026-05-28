# Conservative Event Overlay Paper Tracking Lifecycle

Paper tracking lifecycle turns saved conservative overlay snapshots into a repeatable validation workflow. It remains local, opt-in, and research-only: no production defaults change and no real trades are created.

## Routine

1. Create a snapshot daily or weekly.
2. Wait for the configured horizon, for example 20 calendar days.
3. Check ready snapshots.
4. Evaluate ready snapshots.
5. Review dashboard and risk-level contribution.
6. Export CSV for offline review.

## Endpoints

Lifecycle status:

```bash
curl "http://127.0.0.1:8010/signals/event-aware/conservative-overlay-paper-lifecycle-status"
```

Ready snapshots:

```bash
curl "http://127.0.0.1:8010/signals/event-aware/conservative-overlay-paper-ready?limit=50"
```

Bulk evaluate ready snapshots:

```bash
curl -X POST "http://127.0.0.1:8010/signals/event-aware/conservative-overlay-paper-evaluate-ready?limit=50"
```

Dashboard:

```bash
curl "http://127.0.0.1:8010/signals/event-aware/conservative-overlay-paper-dashboard?limit=20"
```

CSV exports:

```bash
curl "http://127.0.0.1:8010/signals/event-aware/conservative-overlay-paper-snapshots.csv?limit=100"
curl "http://127.0.0.1:8010/signals/event-aware/conservative-overlay-paper-snapshots/1.csv"
curl "http://127.0.0.1:8010/signals/event-aware/conservative-overlay-paper-dashboard.csv"
```

Manual cleanup:

```bash
curl -X DELETE "http://127.0.0.1:8010/signals/event-aware/conservative-overlay-paper-snapshots/1"
```

The dashboard page is:

```text
/signals/event-aware/conservative-overlay-paper-tracking-page
```

## CLI

Run from `backend`:

```bash
python3 -m app.tasks.event_overlay_paper_tracking status
python3 -m app.tasks.event_overlay_paper_tracking create --name daily --limit 100 --horizon-days 20
python3 -m app.tasks.event_overlay_paper_tracking evaluate-ready --limit 50
```

## Metrics

- `baseline_total_pnl_pct`: realized paper PnL using baseline position sizes.
- `overlay_total_pnl_pct`: realized paper PnL using conservative overlay-adjusted sizes.
- `overlay_delta_pnl_pct`: overlay PnL minus baseline PnL.
- `by_risk_level`: contribution grouped by event risk level.
- `cumulative_curve`: cumulative baseline, overlay, and delta by snapshot date.
- `ready_to_evaluate_snapshots`: open or partially evaluated snapshots whose horizon has elapsed.

## Limitations

- Paper trading only.
- No real execution, order book, latency, or liquidity model.
- Evaluation uses local future candles when available.
- Existing assumptions about slippage and proxy outcomes still apply.
- No investment advice.
