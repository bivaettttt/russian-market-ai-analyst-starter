# Event-Aware Setup Research

Event-aware setup research checks whether a technical long setup gains edge when it is confirmed by a news, macro, geopolitical, FX, rates, commodity, dividend, earnings or corporate-action catalyst.

Pure OHLCV setup research improved old consumer candidates, but still did not produce stable positive expectancy. This layer tests the next hypothesis: technical setups alone are not enough; an external catalyst may be required.

## Event Families

- `rates`: key-rate cuts/hikes, easing/tightening, OFZ and rate-sensitive equities.
- `sanctions`: new sanctions or sanctions relief.
- `geopolitics`: escalation, de-escalation and risk-off/risk-on shocks.
- `oil_gas`: oil/gas price or supply shocks.
- `fx`: RUB weakness/strength and exporter/importer impact.
- `dividend`: dividend announcement, approval, cut or cancellation.
- `earnings`: strong or weak operating/financial results.
- `corporate_action`: buyback, SPO/dilution, merger/M&A.
- `macro`: inflation, GDP, PMI and broad macro data.
- `sector_news`: sector-specific policy or demand shocks.
- `ticker_news`: ticker mention without a stronger family classification.

## Mapping Logic

`event_ticker_mapping.py` is deterministic and transparent. It normalizes tags from event title/text/raw analysis, classifies the event family, direction, scope and score, then maps the impact to a ticker/sector/asset type. No external API is called.

For long candidates:

- positive event impact becomes `confirmed`;
- negative event impact becomes `conflict`;
- mixed/neutral/unknown becomes `neutral`;
- no relevant event becomes `none`;
- positive event without active setup becomes `event_only`.

Event score decays by age:

```text
effective_score = raw_score * max(0, 1 - days_since_event / event_decay_days)
```

## Reports

- `by_event_family`: PnL grouped by event family.
- `by_setup_event_combo`: PnL grouped by setup family + event family + direction.
- `best_combinations`: top-ranked combinations by quality, PF, avg return and sample count.
- `bad_combinations`: combinations with enough samples and negative expectancy.
- `sweep`: bounded grid over lookback, decay, minimum event score, confirmation mode and setup mode.

Key fields:

- `profit_factor`: gross wins divided by gross losses.
- `avg_trade_return_pct`: average simulated trade return after simplified costs.
- `event_score`: decayed catalyst score used for confirmation/conflict.
- `quality_label`: `good`, `medium`, `weak`, `bad` or `unstable`.

## If No Historical Events Exist

The endpoint still returns HTTP 200 and `ok=true`, with warnings and recommendation `needs_more_event_data`. In that case the live event layer can remain useful as a diagnostic, but historical validation needs event ingestion/backfill before conclusions are reliable.

## Curl Examples

```bash
curl "http://127.0.0.1:8010/signals/events/coverage?max_events=5000"
```

```bash
curl "http://127.0.0.1:8010/signals/event-aware/research?max_tickers=20&max_samples=1000&max_events=1000&min_signals=10"
```

```bash
curl "http://127.0.0.1:8010/signals/event-aware/research?max_tickers=80&max_samples=3000&max_events=5000&event_lookback_days=7&event_decay_days=14&commission_bps=10&slippage_bps=5"
```

```bash
curl "http://127.0.0.1:8010/signals/event-aware/sweep?max_tickers=80&max_samples=3000&max_events=5000&max_configs=60&min_signals=20"
```

## Limitations

- historical event coverage may be incomplete or absent;
- event classifier and ticker/sector mapping are heuristic;
- no external API is used by the research endpoint;
- daily candle backtest has target/stop ordering ambiguity;
- event timestamp/date granularity can be coarse;
- costs are simplified;
- survivorship and local data coverage bias can remain;
- this does not change production consumer logic.
