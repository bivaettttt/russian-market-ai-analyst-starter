# ML v2 High-Confidence Validation

High-confidence validation checks whether the top ML v2 probability bucket is stable across rolling time splits.

The previous ML v2 evaluation had AUC close to random, but the 60% threshold showed a small positive PnL pocket. A weak global AUC does not always mean a high-confidence bucket is useless: a model can be poorly ranked overall while still isolating a small useful subset. This validation tests that possibility fold by fold.

## Walk-Forward Process

The service builds the ML v2 trade dataset, sorts samples by date, and creates expanding train windows with forward test windows. For each fold it:

- trains a local ML v2 classifier on the train period;
- predicts probabilities on the next test period;
- evaluates thresholds such as `50%`, `55%`, `60%`, `65%`, `70%`;
- computes PnL metrics for selected test samples.

No production signal logic changes.

## Reading `threshold_summary`

- `total_signals`: selected signals across folds.
- `avg_coverage_pct`: average selected share of test samples.
- `avg_trade_return_pct`: average of fold-level selected trade return.
- `avg_profit_factor`: average fold-level profit factor.
- `positive_folds`: folds where selected avg trade return was positive.
- `stable_positive_rate_pct`: positive folds divided by folds with signals.
- `score`: bounded research score that rewards positive PnL/PF and consistency, and penalizes tiny coverage or too few folds.
- `quality_label`: `stable`, `promising`, `weak`, or `unstable`.

## Recommendations

- `use_as_research_gate`: threshold looks stable enough for further research gating, not production.
- `promising_but_unstable`: positive signal exists but sample or fold consistency is weak.
- `reject`: no threshold improves materially.
- `needs_more_data`: there is not enough data/folds/signals.

## Why It Is Not Automatic

Even a stable-looking high-confidence threshold can overfit the available proxy sample. It must be validated with longer walk-forward windows, paper trading, and real saved signal snapshots before any production use.

## Limitations

- High thresholds have small sample risk.
- Labels are proxy trade outcomes.
- Costs are simplified bps inputs.
- Daily candles do not fully resolve intraday target/stop sequence.
- Requires paper trading validation.
- Not investment advice.

## Curl Examples

Quick:

```bash
curl "http://127.0.0.1:8010/signals/ml-v2/high-confidence-validation?max_tickers=20&max_samples=1000&folds=3"
```

Medium:

```bash
curl "http://127.0.0.1:8010/signals/ml-v2/high-confidence-validation?max_tickers=80&max_samples=3000&folds=4&min_train_samples=500&min_test_samples=150&commission_bps=10&slippage_bps=5"
```

Custom thresholds:

```bash
curl "http://127.0.0.1:8010/signals/ml-v2/high-confidence-validation?thresholds=0.55,0.60,0.65,0.70"
```
