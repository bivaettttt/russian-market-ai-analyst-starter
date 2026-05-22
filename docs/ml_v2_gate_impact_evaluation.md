# ML v2 Gate Impact Evaluation

ML v2 gate impact evaluation checks how an ML v2 research gate would have changed historical proxy trade outcomes. It is a research layer only. It does not change production consumer recommendations, position sizing, or ML v1.

## Modes

`diagnostic_only` scores every sample and compares buckets:

- passed: ML v2 probability is above threshold;
- rejected: ML v2 probability is below threshold;
- no trades are filtered in this mode.

`soft_downgrade` simulates a conservative workflow where rejected long candidates are downgraded to no-trade/watch for evaluation. PnL is measured only on active passed samples. This is equivalent to assuming downgraded trades are not opened.

`hard_gate` keeps only samples with ML v2 probability above threshold. Rejected samples are filtered out.

## Leakage Warning

This endpoint uses the current saved ML v2 artifact. If that artifact was trained on the same historical period being evaluated, results may contain training leakage. The ML v2 high-confidence validation endpoint remains the better evidence for walk-forward stability.

## Metrics

- `selected_samples`: samples kept by the mode/threshold.
- `coverage_pct`: selected samples divided by baseline samples.
- `avg_trade_return_delta_pct`: selected average trade return minus baseline.
- `profit_factor_delta`: selected profit factor minus baseline.
- `stop_hit_delta_pct`: selected stop-hit rate minus baseline. Negative is better.
- `avoided_losses`: losing samples removed by the gate.
- `missed_wins`: winning samples removed by the gate.
- `recommendation`: high-level interpretation of the best row.

## Train Artifact

If the artifact is missing, the endpoint returns HTTP 200 with `ok=false` and `recommendation=artifact_missing`.

Train locally:

```bash
cd backend
python3 -m app.tasks.train_ml_v2 \
  --label positive_trade_return \
  --max-tickers 120 \
  --max-samples 10000 \
  --horizon 30
```

The artifact is saved in `backend/data/`, which is ignored by git.

## Curl Examples

No artifact or quick status:

```bash
curl "http://127.0.0.1:8010/signals/ml-v2/gate-impact?max_tickers=5&max_samples=300&min_signals=10"
```

Default thresholds with artifact:

```bash
curl "http://127.0.0.1:8010/signals/ml-v2/gate-impact?max_tickers=80&max_samples=3000&min_signals=30"
```

Custom thresholds:

```bash
curl "http://127.0.0.1:8010/signals/ml-v2/gate-impact?thresholds=0.50,0.55,0.60,0.65,0.70"
```

Hard gate only:

```bash
curl "http://127.0.0.1:8010/signals/ml-v2/gate-impact?gate_modes=hard_gate&thresholds=0.55,0.60"
```

## Limitations

- Research only, not a production gate.
- Artifact-based evaluation may leak training information.
- Uses proxy labels from daily candles.
- Costs are simplified.
- Daily candles cannot fully resolve intraday target/stop sequencing.
- Needs paper trading before production use.
- Not investment advice.
