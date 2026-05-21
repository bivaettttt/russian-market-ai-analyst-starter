# Local MOEX Data Bootstrap

Local MOEX data bootstrap fills the local database with a reproducible instrument universe and daily OHLCV candles from public MOEX ISS endpoints.

It is a data ingestion layer. It does not change model thresholds, signal rules, risk logic or production decisions.

## Data Source

The bootstrap uses public MOEX ISS endpoints:

- securities: `/iss/engines/stock/markets/{market}/boards/{board}/securities.json`
- candles: `/iss/engines/stock/markets/shares/boards/{board}/securities/{SECID}/candles.json`

No paid API or OpenAI-compatible dependency is used.

## Commands

From the repository:

```bash
cd /Users/bivaettttt/Desktop/russian-market-ai-analyst-starter
source backend/.venv/bin/activate
cd backend
```

Dry-run:

```bash
python3 -m app.tasks.bootstrap_market_data --dry-run --max-tickers 3 --days 30
```

Small quick bootstrap:

```bash
python3 -m app.tasks.bootstrap_market_data --max-instruments 50 --max-tickers 5 --days 120 --tickers SBER,GAZP,LKOH
```

Full local bootstrap:

```bash
python3 -m app.tasks.bootstrap_market_data --max-instruments 300 --max-tickers 100 --days 900
```

Candles only:

```bash
python3 -m app.tasks.bootstrap_market_data --skip-universe --max-tickers 100 --days 900
```

## Verification

Start the app, then run:

```bash
curl "http://127.0.0.1:8010/signals/data-coverage?max_tickers=100&min_history=60&horizon=20"
```

Expected after a successful bootstrap:

- `signal_eligible_count > 0`
- `tickers_with_candles > 0`
- `usable_tickers > 0`
- `total_possible_samples > 0`

The read-only endpoint `/signals/data-bootstrap-status` returns current coverage and suggested commands.

## Safety

- Dry-run fetches and parses data but rolls back DB changes.
- Per-ticker candle failures are collected and do not stop the full batch.
- Requests use timeout and retry.
- `sleep_sec` throttles candle requests.
- Existing instruments/candles are upserted, not deleted.

## Limitations

- Depends on public MOEX ISS availability.
- Uses daily data, not intraday.
- Does not adjust for corporate actions unless MOEX ISS data already reflects them.
- The universe is current and can introduce survivorship bias.
- Candle import does not guarantee a clean survivorship-free historical universe.
