# ML v2 Gate Walk-forward

ML v2 gate walk-forward is the leakage-safe check for the experimental ML v2 gate. It answers whether the gate improves future test-period trade outcomes when each fold trains only on earlier data.

## Why This Exists

Artifact-based gate impact can overstate results because the saved artifact may have seen the same samples it later scores. Walk-forward avoids that specific leakage:

- train ML v2 on the fold train period;
- score only the future test period;
- evaluate baseline vs gate modes on that test period;
- aggregate mode/threshold stability across folds.

## Related Evaluations

- Gate impact: artifact-based, useful for quick local inspection, but can leak.
- High-confidence validation: checks ML v2 probability thresholds on walk-forward folds.
- Gate walk-forward: checks full gate modes, including coverage, avoided losses, missed wins, and baseline deltas.

## Gate Modes

`diagnostic_only`: keeps all test samples and compares passed vs rejected buckets.

`soft_downgrade`: treats rejected samples as downgraded/no-trade for historical PnL. It assumes downgraded trades are not opened.

`hard_gate`: keeps only samples with ML v2 probability above threshold.

## Reading Results

- `avg_selected_trade_return_pct`: average trade return for selected samples across folds.
- `avg_selected_profit_factor`: average selected profit factor across folds.
- `stable_positive_rate_pct`: share of folds where selected average return is positive.
- `positive_folds`: count of folds with positive selected average return.
- `avg_coverage_pct`: average selected coverage across folds.
- `avg_avoided_losses`: average losing samples filtered per fold.
- `avg_missed_wins`: average winning samples filtered per fold.
- `recommendation`: high-level research interpretation.

A gate is only a candidate for experimental production if it has:

- profit factor above `1.08`;
- average selected trade return above zero;
- stable positive folds;
- enough coverage/signals;
- paper trading confirmation.

## Curl Examples

Quick:

```bash
curl "http://127.0.0.1:8010/signals/ml-v2/gate-walk-forward?max_tickers=20&max_samples=1000&folds=3"
```

Full local run:

```bash
curl "http://127.0.0.1:8010/signals/ml-v2/gate-walk-forward?max_tickers=80&max_samples=3000&folds=4&min_train_samples=500&min_test_samples=150&min_signals=50"
```

Hard gate only:

```bash
curl "http://127.0.0.1:8010/signals/ml-v2/gate-walk-forward?gate_modes=hard_gate&thresholds=0.55,0.60"
```

Custom thresholds:

```bash
curl "http://127.0.0.1:8010/signals/ml-v2/gate-walk-forward?thresholds=0.50,0.55,0.60,0.65,0.70"
```

## Limitations

- Labels are proxy daily-candle outcomes.
- Costs are simplified.
- Daily candles cannot fully resolve intraday target/stop sequence.
- High thresholds can have small sample risk.
- This does not modify production consumer logic.
- Paper trading is required before production use.
- Not investment advice.
