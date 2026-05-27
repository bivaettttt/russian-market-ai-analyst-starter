# Historical Event Bootstrap

Event-aware setup research returned `event_samples=0` because the local event table only had current events around 2026-05-14. Historical candle samples need event dates that overlap the backtest window.

This bootstrap imports a small curated seed into the existing `MarketEvent` table. It is offline, deterministic and idempotent. It does not call external APIs and does not change production consumer recommendations.

## Seed

Default file:

```text
backend/app/data/seed/historical_events_seed.json
```

The seed covers 2022-2026 and includes research markers for:

- key-rate hikes/cuts/holds;
- geopolitics and risk-off markers;
- sanctions risk;
- RUB strength/weakness;
- oil/gas and exporter catalysts;
- dividend season and selected large-cap dividend markers;
- earnings markers for major liquid names;
- broad macro/sector policy markers.

The seed is not a complete verified event history. It is a research bootstrap that should later be expanded or replaced with source-based ingestion.

## Commands

Dry run:

```bash
cd backend
python3 -m app.tasks.bootstrap_historical_events --dry-run
```

Real import:

```bash
python3 -m app.tasks.bootstrap_historical_events
```

Replace existing curated seed rows only:

```bash
python3 -m app.tasks.bootstrap_historical_events --replace-existing-seed
```

Custom JSON/CSV:

```bash
python3 -m app.tasks.bootstrap_historical_events --seed-path app/data/seed/historical_events_seed.json
```

## Verify

```bash
curl "http://127.0.0.1:8010/signals/events/coverage?max_events=10000"
```

```bash
curl "http://127.0.0.1:8010/signals/event-aware/research?max_tickers=80&max_samples=3000&max_events=10000&min_signals=20"
```

Targets after import:

- `total_events` above 100 when combined with existing live events;
- `date_range` starts in 2022;
- event-aware research has `event_samples > 0`.

## Caveats

- curated seed is research bootstrap data, not an official data source;
- historical coverage is incomplete and should be expanded;
- event timestamps use daily granularity;
- daily candle backtest has intraday target/stop ambiguity;
- this is not investment advice and not production signal logic.
