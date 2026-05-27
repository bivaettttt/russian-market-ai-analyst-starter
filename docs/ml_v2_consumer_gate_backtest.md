# ML v2 Consumer Gate Backtest

`/signals/consumer/ml-v2-gate-backtest` is a research-only historical evaluation for the experimental ML v2 decision gate on proxy consumer signals.

It checks whether ML v2 improves active consumer long candidates after the existing consumer decision layer has already reconstructed a historical action. It does not change production defaults, does not enable ML v2 by default, and does not replace ML v1.

## How It Differs

- ML v2 high-confidence validation checks probability thresholds for ML v2 as a standalone research model.
- ML v2 gate impact evaluates gate behavior on ML v2 trade dataset rows, usually with the saved artifact.
- ML v2 gate walk-forward validates the gate leakage-safely on ML v2 trade outcomes.
- Current snapshot compare shows how today's consumer list would change with the experimental gate.
- Consumer gate backtest checks the gate on historical/proxy consumer actions and active trade simulation.

## Gate Modes

- `diagnostic_only`: ML v2 is scored, but historical action is not changed. The response includes passed vs rejected PnL buckets.
- `soft_downgrade`: rejected long candidates become `watch_ml_v2_rejected` and are treated as no active trade.
- `hard_gate`: rejected long candidates become `avoid_ml_v2_rejected` and are treated as no active trade.

The gate does not upgrade avoid/watch/risk/downside actions to buys.

## Prediction Modes

`use_leakage_safe_predictions=true` trains fold models only on past rows and scores future rows. This mode does not require a saved ML v2 artifact.

`use_leakage_safe_predictions=false` uses the current saved ML v2 artifact. If the artifact is missing, the endpoint returns HTTP 200 with `ok=false` and an `artifact_missing` style error. Artifact mode can contain training leakage if the artifact saw the evaluated period.

## Historical Consumer Actions

Historical actions are proxy reconstructed from candle-only consumer audit samples. The service uses the existing proxy consumer decision gate and adaptive trade policy, then maps long candidates centrally:

- `buy`
- `consider_buy`
- `watch_ml_confirmed`
- legacy `buy_watch` / `watch_buy`

Avoid, risk, downside, bad-RR, neutral watch, and ML veto actions are not treated as active long trades.

## Reading The Metrics

- `coverage_pct`: selected active trades divided by baseline active trades.
- `selected_active_trades`: trades still active after the gate.
- `avg_trade_return_delta_pct`: selected average trade return minus baseline active-trade average.
- `profit_factor_delta`: selected PF minus baseline PF.
- `avoided_losses`: rejected baseline active trades with negative trade return.
- `missed_wins`: rejected baseline active trades with positive trade return.
- `recommendation`: research interpretation, not a production switch.

`promising_experimental_gate` requires a good leakage-safe result, positive selected return, PF at least 1.08, and at least 10% coverage. Weak or artifact-only positive results stay `research_only`.

## Limitations

- Historical consumer signals are proxy reconstructed.
- Outcomes are proxy labels from daily candles.
- Daily candles do not fully resolve intraday target/stop sequence.
- Costs are simplified commission/slippage assumptions.
- Production default behavior is unchanged.
- Paper trading validation is required before production use.

## Curl Examples

Quick:

```bash
curl "http://127.0.0.1:8010/signals/consumer/ml-v2-gate-backtest?max_tickers=20&max_samples=1000&min_signals=10&folds=2"
```

Full leakage-safe:

```bash
curl "http://127.0.0.1:8010/signals/consumer/ml-v2-gate-backtest?max_tickers=80&max_samples=3000&min_signals=50&folds=4&commission_bps=10&slippage_bps=5"
```

Artifact mode:

```bash
curl "http://127.0.0.1:8010/signals/consumer/ml-v2-gate-backtest?use_leakage_safe_predictions=false&max_tickers=80&max_samples=3000"
```

Hard gate only:

```bash
curl "http://127.0.0.1:8010/signals/consumer/ml-v2-gate-backtest?gate_modes=hard_gate&thresholds=0.55,0.60&max_tickers=80&max_samples=3000"
```
