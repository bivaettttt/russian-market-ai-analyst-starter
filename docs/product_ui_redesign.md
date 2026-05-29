# Product UI Redesign

The UI is now split into two layers:

- User-facing product layer: `/signals`, ticker detail, Live Validation, Quality, Paper Tracking, Daily Ops and Market Data.
- Advanced research layer: `/signals/research-hub-page` and calibration/backtest/research pages.

## Design Goals

- Make `/signals` understandable without reading debug fields.
- Put conservative event overlay and paper exposure in clear cards.
- Keep raw diagnostics available, but collapsed by default.
- Prevent text overflow on desktop, tablet and mobile.
- Preserve all backend calculations, JSON contracts and production defaults.

## Main Page Structure

- `/signals`: status strip, compact filters, broker-style signal cards and collapsed advanced diagnostics.
- `/ticker/{ticker}` and `/tickers/{ticker}`: ticker overview, signal/risk/exposure cards, concise reasons and collapsed technical audit.
- `/signals/live-paper-validation/page`: official paper-validation cockpit with latest official snapshot and next evaluation date.
- `/signals/event-aware/conservative-overlay-quality-report-page`: official-only quality report with KPI cards and advanced tables collapsed.
- `/signals/event-aware/conservative-overlay-paper-tracking-page`: snapshot hygiene, official/test/legacy filters and safe cleanup.
- `/signals/daily-ops/page`: operational daily checklist.
- `/signals/daily-ops/market-refresh-report-page`: MOEX candle freshness report.

## Overflow Safety

The shared design system includes:

- `product-shell`, `signal-card`, `ticker-card`, `metric-card`;
- `table-wrap` for horizontal table scroll;
- `line-clamp-*` utilities;
- global `overflow-wrap: anywhere` safeguards;
- mobile single-column layout for cards and signal rows.

## Validation Checklist

Open:

- `http://127.0.0.1:8010/signals`
- `http://127.0.0.1:8010/ticker/SBER`
- `http://127.0.0.1:8010/signals/live-paper-validation/page`
- `http://127.0.0.1:8010/signals/event-aware/conservative-overlay-quality-report-page`
- `http://127.0.0.1:8010/signals/event-aware/conservative-overlay-paper-tracking-page`

Check that no page has horizontal overflow, raw diagnostics are collapsed, and product pages do not expose research/debug fields above the fold.

This redesign does not place trades, does not change production defaults and is not investment advice.
