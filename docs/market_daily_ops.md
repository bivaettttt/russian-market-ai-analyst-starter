# Market Daily Ops

Market Daily Ops is the local operations workflow for Paper Validation Alpha. It refreshes local MOEX candles, creates a conservative event overlay paper snapshot without duplicates, evaluates ready snapshots, and returns a compact quality summary.

It does not change production consumer recommendations, does not enable the overlay by default, and does not create real trades.

## Daily Workflow

1. Refresh recent MOEX candles.
2. Check market data freshness.
3. Create today's conservative overlay snapshot if it does not already exist.
4. Evaluate snapshots whose horizon has elapsed.
5. Review the quality report.
6. Export CSV if needed.

## CLI

Run from `backend`:

```bash
python3 -m app.tasks.market_daily_ops status
python3 -m app.tasks.market_daily_ops refresh --max-tickers 150 --days 120
python3 -m app.tasks.market_daily_ops run --name daily --limit 100 --horizon-days 20
python3 -m app.tasks.market_daily_ops run --dry-run
python3 -m app.tasks.market_daily_ops run --no-refresh
python3 -m app.tasks.market_daily_ops run --force-refresh
```

Use `--json` to print the full machine-readable result.

## API

```text
GET  /signals/daily-ops/status
GET  /signals/daily-ops/market-data-freshness
GET  /signals/daily-ops/market-refresh-report
GET  /signals/daily-ops/market-refresh-notification
GET  /signals/daily-ops/market-refresh-report.csv
POST /signals/daily-ops/refresh-market-data
POST /signals/daily-ops/run
GET  /signals/daily-ops/page
```

The stricter official paper-validation workflow is documented in `docs/live_paper_validation_start.md`.

Safe dry run:

```bash
curl -X POST "http://127.0.0.1:8010/signals/daily-ops/run?dry_run=true&refresh_market_data=false&limit=10"
```

Full local run without market refresh:

```bash
curl -X POST "http://127.0.0.1:8010/signals/daily-ops/run?name=daily&refresh_market_data=false&limit=100&horizon_days=20"
```

## Cron Or Launchd Example

Example command only; nothing is installed automatically:

```bash
cd /Users/bivaettttt/Desktop/russian-market-ai-analyst-starter/backend
python3 -m app.tasks.market_daily_ops run --name daily --limit 100 --horizon-days 20 --json
```

## Guardrails

- Same-day snapshots are deduped by name, config, limit, horizon, and mode.
- GET endpoints are read-only.
- POST endpoints may write, except `dry_run=true`.
- If MOEX refresh fails, the workflow returns a degraded result with warnings instead of raising an unhandled stack trace.
- Stale market data and missing future candles are surfaced as warnings.

## Limitations

- Paper validation only.
- MOEX availability and local candle quality can affect the result.
- Evaluation uses local future candles and close-to-close proxy logic.
- No real execution, order book, latency, or liquidity model.
- No investment advice.
