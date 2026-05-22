# ML v2 Experimental Decision Gate

ML v2 experimental decision gate is an explicit opt-in mode for consumer signals. It uses the ML v2 probability threshold as a research gate for long candidates, but production defaults remain unchanged.

The gate exists because leakage-safe ML v2 gate walk-forward found a promising research configuration: threshold 55%, profit factor 1.151, average trade return +0.22%, and positive folds 3/4. This is enough for an experiment, not enough for automatic production enforcement.

## Modes

- `diagnostic_only`: compute ML v2 status and show it in forecast/audit/UI. Action and recommendation are unchanged.
- `soft_downgrade`: if a long-positive candidate is rejected by ML v2, downgrade it to `watch_ml_v2_rejected`.
- `hard_gate`: if a long-positive candidate is rejected by ML v2, change it to `avoid_ml_v2_rejected`.

The gate never upgrades an avoid/risk/downside signal. If the ML v2 artifact is missing or scoring fails, action is not changed.

## Fields

- `ml_v2_gate_mode`
- `ml_v2_gate_effect`
- `ml_v2_original_action`
- `ml_v2_original_recommendation`
- `ml_v2_final_action_changed`
- `ml_v2_gate_blocked_reason`
- `ml_v2_gate_research_basis`
- `signal_audit.layer_scores.ml_v2_research_gate`

## Train Artifact

```bash
cd backend
python3 -m app.tasks.train_ml_v2 --label positive_trade_return --max-tickers 120 --max-samples 10000
```

Runtime artifacts are not committed. Without an artifact, endpoints return `ml_v2_gate_status=not_available`.

## Examples

```bash
curl "http://127.0.0.1:8010/signals/consumer/SBER.json?use_ml_v2_research_gate=true&ml_v2_gate_mode=diagnostic_only"
curl "http://127.0.0.1:8010/signals/consumer.json?limit=50&use_ml_v2_research_gate=true&ml_v2_gate_mode=soft_downgrade"
curl "http://127.0.0.1:8010/signals/consumer/ml-v2-gate-compare?limit=50&ml_v2_gate_mode=soft_downgrade"
```

## Warnings

This is experimental and diagnostic/research-oriented. Do not use it as a production default without paper trading and further monitoring. It is not investment advice.

