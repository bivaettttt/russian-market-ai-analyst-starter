# Composite Rule Calibration

Composite rule calibration is a research layer for testing combinations of entry conditions after adaptive target/stop calibration.

Candidate filter calibration checked mostly single pockets. That is useful diagnostics, but the latest run showed no material improvement from single ticker or bucket filters. Composite calibration checks whether combinations like probability + RR + regime + liquidity improve trade PnL while keeping enough coverage.

## Rule Families

The current grid is intentionally bounded and deterministic:

- probability + RR thresholds;
- probability + market regime;
- probability + volatility/liquidity;
- ML proxy probability + rule probability;
- audit confidence + probability;
- RR + volatility;
- market regime + ML proxy + RR;
- news/macro penalty exclusions;
- conservative high-quality rule;
- aggressive coverage rule.

The endpoint does not run an unbounded Cartesian search. Use `max_rules` to cap runtime.

## How To Read The Output

- `selected_samples`: trades selected by the composite rule.
- `coverage_pct`: selected trades divided by baseline samples.
- `selected_avg_trade_return_pct`: realized average trade PnL after costs.
- `selected_profit_factor`: gross wins divided by gross losses for selected trades.
- `avg_trade_return_delta_pct`: selected average PnL minus baseline average PnL.
- `stop_hit_delta_pct`: selected stop-hit rate minus baseline stop-hit rate; negative is better.
- `score`: bounded research score that rewards positive expectancy, profit factor, win-rate lift, lower stop-hit, and penalizes tiny coverage.
- `quality_label`: `good`, `medium`, `weak`, or `unstable`.

## Why Rules Are Not Applied Automatically

Composite rules can easily overfit a proxy historical sample. A rule that looks good in this table must be checked with walk-forward validation and, ideally, paper trading on saved real signal snapshots before it becomes production logic.

This endpoint only returns diagnostics and ranked candidates. It does not change consumer signal thresholds or decision gates.

## Limitations

- Proxy historical data does not replay full live news, global macro, or ML context.
- Costs are simplified as commission/slippage bps inputs.
- Daily candles do not tell whether target or stop happened first inside the same day.
- Current universe can include survivorship bias.
- Small selected samples can produce unstable results.
- Results are not investment advice.

## Curl Examples

Quick:

```bash
curl "http://127.0.0.1:8010/signals/consumer/composite-rule-calibration?max_tickers=10&max_samples=300&max_rules=40"
```

Medium:

```bash
curl "http://127.0.0.1:8010/signals/consumer/composite-rule-calibration?max_tickers=80&max_samples=3000&max_rules=120&commission_bps=10&slippage_bps=5"
```

Lower `min_trades` for exploratory diagnostics:

```bash
curl "http://127.0.0.1:8010/signals/consumer/composite-rule-calibration?max_tickers=80&max_samples=3000&max_rules=120&min_trades=30"
```

Higher costs:

```bash
curl "http://127.0.0.1:8010/signals/consumer/composite-rule-calibration?max_tickers=80&max_samples=3000&max_rules=120&commission_bps=20&slippage_bps=10"
```
