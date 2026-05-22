# ML v2 Research Gate Integration

ML v2 research gate is a diagnostic layer for consumer signals. It does not replace ML v1 and does not change production recommendations by default.

The gate uses the ML v2 trade PnL model trained on proxy trade outcomes. The default threshold is 55%, because ML v2 high-confidence validation found this bucket as the best research candidate:

- average trade return: `+0.22%`
- average profit factor: `1.151`
- positive folds: `3/4`
- total signals: `339`
- recommendation: `use_as_research_gate`

## Train Artifact

The consumer endpoint works even when no artifact exists. Missing artifact responses use `ml_v2_gate_status=not_available` and include the training command.

To train the local research artifact:

```bash
cd backend
python3 -m app.tasks.train_ml_v2 \
  --label positive_trade_return \
  --max-tickers 120 \
  --max-samples 10000 \
  --horizon 30 \
  --policy-id atr_t1_5_s1_6_h30_rr0_8
```

The artifact is saved under `backend/data/`, which is ignored by git.

## API Usage

Single ticker:

```bash
curl "http://127.0.0.1:8010/signals/consumer/SBER.json?use_ml_v2_research_gate=true"
```

Signal list:

```bash
curl "http://127.0.0.1:8010/signals/consumer.json?limit=20&use_ml_v2_research_gate=true&ml_v2_gate_threshold_pct=55"
```

## Response Fields

- `ml_v2_probability_pct`: predicted probability for positive trade return.
- `ml_v2_gate_threshold_pct`: threshold used by the diagnostic gate.
- `ml_v2_gate_passed`: `true`, `false`, or `null` when disabled/not available.
- `ml_v2_gate_status`: `passed`, `rejected`, `not_available`, `error`, or `disabled`.
- `ml_v2_gate_reason`: compact explanation.
- `ml_v2_research_note`: why the layer exists and why it is diagnostic-only.
- `signal_audit.layer_scores.ml_v2_research_gate`: audit entry for the research layer.

## Limitations

- This is a research gate, not production decision logic.
- The artifact may be absent on a clean checkout.
- Validation uses proxy daily-candle outcomes and simplified costs.
- Daily candles do not fully resolve intraday target/stop ordering.
- The gate needs paper trading validation before any production use.
- This is not investment advice.
