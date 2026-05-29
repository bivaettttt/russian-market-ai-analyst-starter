# Live Paper Validation Start

This stage starts the stricter official paper validation workflow for the conservative event overlay. It is still paper validation only: no production recommendations change and no real trades are created.

## Daily Ops Vs Live Paper Validation Start

- Daily Ops is the operational workflow for local market refresh, snapshot creation, ready evaluation, and quality reporting.
- Live Paper Validation Start is stricter. By default it refuses to create an official snapshot unless market data is fresh.

## Market Freshness Requirement

Official snapshots require fresh local candles by default. If candles are stale, the start workflow returns:

```text
status=blocked
blocked_reason=market_data_stale
next_steps=refresh_market_data, verify_market_freshness, rerun_live_paper_validation_start
```

Use `--allow-stale` or `require_fresh_market_data=false` only for manual diagnostics.

## CLI

Run from `backend`:

```bash
python3 -m app.tasks.market_daily_ops status
python3 -m app.tasks.market_daily_ops refresh --max-tickers 150 --days 120
python3 -m app.tasks.market_daily_ops run --name daily --limit 100 --horizon-days 20

python3 -m app.tasks.live_paper_validation status
python3 -m app.tasks.live_paper_validation start --dry-run
python3 -m app.tasks.live_paper_validation start --name official-daily --limit 100 --horizon-days 20
python3 -m app.tasks.live_paper_validation start --no-refresh
python3 -m app.tasks.live_paper_validation start --allow-stale
```

## API

```text
GET  /signals/daily-ops/market-refresh-report
GET  /signals/daily-ops/market-refresh-notification
GET  /signals/daily-ops/market-refresh-report.csv
GET  /signals/daily-ops/market-refresh-report-page

GET  /signals/live-paper-validation/status
GET  /signals/live-paper-validation/official-summary
POST /signals/live-paper-validation/start
GET  /signals/live-paper-validation/page
```

Safe dry run:

```bash
curl -X POST "http://127.0.0.1:8010/signals/live-paper-validation/start?dry_run=true&refresh_market_data=false&require_fresh_market_data=false&limit=10"
```

## Recommended Routine

1. Refresh market data after local MOEX candle update.
2. Verify `/signals/daily-ops/market-refresh-report`.
3. Start official daily snapshot only when data is fresh.
4. Evaluate ready snapshots.
5. Review the official-only quality report weekly.

Official snapshot hygiene is documented in `docs/official_live_validation_hygiene.md`. Test and legacy snapshots are still available for audit, but official quality views use `official_only=true` by default.

## Launchd Or Cron Examples

Example only; nothing is installed automatically:

```bash
cd /Users/bivaettttt/Desktop/russian-market-ai-analyst-starter/backend
python3 -m app.tasks.live_paper_validation start --name official-daily --limit 100 --horizon-days 20 --json
```

## Limitations

- MOEX availability can block refresh.
- Local candle freshness determines official start readiness.
- Paper validation only.
- No real execution or order-book simulation.
- No investment advice.
