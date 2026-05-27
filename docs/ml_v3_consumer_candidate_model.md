# ML v3 Consumer Candidate Model

ML v3 exists because ML v2 did not improve the consumer ML v2 gate backtest. ML v2 was trained on generic trade-PnL samples, while the consumer layer already filters the market into a narrower distribution of long candidates. That distribution mismatch made ML v2 promising on a generic dataset but weak on actual consumer-candidate actions.

ML v3 trains only on historical samples that the consumer layer would have treated as long candidates: `buy`, `consider_buy`, `watch_ml_confirmed`, and legacy `buy_watch` / `watch_buy`. Plain `watch` is excluded by default and can be included only with `include_watch_candidates=true`.

## Dataset

Endpoint: `/signals/ml-v3/consumer-candidate/dataset-summary`

The dataset uses proxy historical consumer samples, adaptive trade policy outcomes, and stable numeric features. Future candles are used only for labels/outcomes, not for features.

Labels:

- `positive_trade_return`: trade return is greater than zero.
- `good_trade`: trade return is at least `0.5%`.
- `avoid_loss`: trade return is at least `-0.3%`.
- `target_hit`: outcome is `target_hit`.
- `avoid_stop`: outcome is not `stop_hit`.

Feature groups:

- Consumer decision features: target/rule probability, proxy ML probability, risk/reward, reliability, audit confidence, action encoding.
- Technical features: returns, moving-average gaps, volatility, ATR proxy, range position, liquidity/value ratios.
- Trade setup features: target, stop, target/stop ratio, policy encoding, setup RR.
- Market/regime features: regime encoding, regime score, downside pressure, breadth, trend.
- News/macro features: adjustment fields when available, otherwise zero.
- Instrument features: asset type, sector, liquidity bucket, volatility bucket.

## Evaluation

Endpoint: `/signals/ml-v3/consumer-candidate/evaluation`

Evaluation uses a time-based train/test split. It reports AUC, Brier, baseline candidate PnL, threshold coverage, selected return, profit factor, win rate, stop-hit rate, avoided losses and missed wins.

## Walk-Forward

Endpoint: `/signals/ml-v3/consumer-candidate/walk-forward`

Walk-forward is the leakage-safer validation path. Each fold trains only on earlier consumer candidates and scores future candidates. It compares:

- `diagnostic_only`: no filtering, but passed/rejected buckets are shown.
- `soft_downgrade`: rejected candidates are treated as no active trade in research simulation.
- `hard_gate`: rejected candidates are treated as avoided trades.

Recommendation values:

- `promising_ml_v3_gate`: stable walk-forward edge with positive return and PF at least 1.08.
- `research_only`: positive but weaker or lower-coverage evidence.
- `reject`: no material improvement.
- `needs_more_data`: insufficient candidate samples/folds.

## Curl Examples

Dataset:

```bash
curl "http://127.0.0.1:8010/signals/ml-v3/consumer-candidate/dataset-summary?max_tickers=80&max_samples=3000"
```

Evaluation:

```bash
curl "http://127.0.0.1:8010/signals/ml-v3/consumer-candidate/evaluation?max_tickers=80&max_samples=3000&label=positive_trade_return"
```

Walk-forward:

```bash
curl "http://127.0.0.1:8010/signals/ml-v3/consumer-candidate/walk-forward?max_tickers=80&max_samples=3000&folds=4&min_train_samples=300&min_test_samples=100&min_signals=30"
```

Small artifact training:

```bash
cd backend
python3 -m app.tasks.train_ml_v3_consumer_candidate --max-tickers 10 --max-samples 500 --label positive_trade_return
```

## Limitations

- Historical consumer actions are proxy reconstructed.
- Costs and fills are simplified.
- Daily candles have target/stop sequencing ambiguity.
- Local universe can contain survivorship and coverage bias.
- ML v3 is not production-integrated yet.
- Paper trading is required before any experimental gate.
