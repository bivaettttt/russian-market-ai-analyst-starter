# Conservative Event Overlay Quality Report

This layer turns conservative event overlay paper tracking into a daily validation workflow. It does not change production consumer recommendations and does not create real trades.

## Why It Exists

The conservative overlay was calibrated as a paper/research risk layer. A single snapshot shows current exposure only. The quality report accumulates stored snapshots, evaluates them after the configured horizon, and compares baseline exposure against overlay-adjusted exposure.

## Daily Workflow

1. Run the daily workflow after market data is updated.
2. Create today's snapshot if one does not already exist.
3. Evaluate snapshots whose horizon has elapsed.
4. Review quality report and problem tickers.
5. Export CSV for offline review.

CLI:

```bash
cd backend
python3 -m app.tasks.market_daily_ops run --name daily --limit 100 --horizon-days 20
python3 -m app.tasks.event_overlay_paper_tracking daily-run --name daily --limit 100 --horizon-days 20 --evaluate-ready
python3 -m app.tasks.event_overlay_paper_tracking status
python3 -m app.tasks.event_overlay_paper_tracking create --name daily --limit 100 --horizon-days 20
python3 -m app.tasks.event_overlay_paper_tracking evaluate-ready --limit 50
```

For the full market-refresh + paper-tracking workflow, use `docs/market_daily_ops.md`.

## Endpoints

```text
GET  /signals/event-aware/conservative-overlay-quality-report
GET  /signals/event-aware/conservative-overlay-quality-report-page
GET  /signals/event-aware/conservative-overlay-notification-summary
GET  /signals/event-aware/conservative-overlay-data-health
POST /signals/event-aware/conservative-overlay-daily-run
GET  /signals/event-aware/conservative-overlay-quality-report.csv
GET  /signals/daily-ops/status
POST /signals/daily-ops/run
```

Existing tracking endpoints remain available for lifecycle status, snapshots, dashboard, evaluation, and cleanup.

## Metrics

- `baseline_total_pnl_pct`: realized paper PnL using baseline position sizes.
- `overlay_total_pnl_pct`: realized paper PnL using overlay-adjusted position sizes.
- `overlay_delta_pnl_pct`: overlay PnL minus baseline PnL.
- `cumulative_curve`: baseline, overlay, and delta accumulated by snapshot date.
- `by_risk_level`: contribution grouped by event risk level.
- `top_positive_contributors`: rows where overlay improved paper PnL most.
- `top_negative_contributors`: rows where overlay hurt paper PnL most.
- `problem_tickers`: repeated negative overlay delta or missed-upside candidates.

## Notification Summary

The notification endpoint returns compact JSON with:

- status;
- message;
- key metrics;
- recommended next action;
- warnings.

It is intended for local/manual notification workflows, not external API delivery.

## Guardrails

- Daily run uses same-day dedupe by default.
- GET endpoints are read-only.
- Write actions are explicit POST endpoints or CLI commands.
- Health checks warn about stale market data, missing snapshots, missing event coverage, and ready snapshots without enough future candles.

## Limitations

- Paper tracking only.
- No real execution, order book, latency, or liquidity model.
- Future candles are required for evaluation.
- Close-to-close results are validation proxies.
- No investment advice.

Recommended operating routine: run daily after local market data update, review quality weekly, and collect at least 4-8 weeks of live paper snapshots before making a product decision.
