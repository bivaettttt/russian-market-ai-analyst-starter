# Expectancy Breakdown Diagnostics

Expectancy breakdown is a research diagnostic layer for the consumer signal validation engine. It splits proxy trade PnL by model segments to show where the system already has positive expectancy and where it consistently loses money.

It does not change production decision logic, thresholds, market regime gates, position sizing, or signal actions.

## Why Expectancy Matters

Hit-rate alone can be misleading. A bucket can win often but lose money if losses are larger than wins, and a lower hit-rate bucket can still be useful when payoff is strong.

The key metrics are:

- `avg_trade_return_pct`: average realized proxy trade return after target/stop/timeout and optional bps costs.
- `profit_factor`: gross gains divided by gross losses.
- `expectancy_pct`: average trade return; same interpretation as expected return per trade in this proxy setup.
- `win_rate_pct`: useful context, but not enough by itself.
- `target_hit_rate_pct`, `stop_hit_rate_pct`, `timeout_rate_pct`: explain how the PnL was produced.

## Dimensions

The endpoint currently breaks down expectancy by:

- `action`
- `ticker`
- `sector`
- `asset_type`
- `market_regime`
- `volatility_bucket`
- `liquidity_bucket`
- `probability_bucket`
- `ml_probability_bucket`
- `rr_bucket`
- `audit_confidence`
- `audit_final_verdict`
- `blocked_by`
- `news_effect`
- `macro_effect`
- `global_event_tags`
- `trade_policy_type`

Missing fields are placed into `unknown` or `none` buckets so diagnostics do not fail on incomplete proxy samples.

## Reading Positive And Negative Pockets

`positive_pockets` are buckets with enough samples, positive average trade return, and `profit_factor > 1.05`.

`negative_pockets` are buckets with enough samples, negative average trade return, and `profit_factor < 0.95`.

Buckets with fewer than `min_bucket_samples` are marked `unstable` and are not used for strong candidate filters or boosts.

## Candidate Filters And Boosts

`candidate_filters` are simple research rules generated from negative buckets, for example:

`exclude volatility_bucket=extreme`

`candidate_boosts` are simple research preferences generated from positive buckets, for example:

`prefer market_regime=risk_on`

These are hypotheses for validation. They are not applied automatically because a segment can be overfit, sample-limited, correlated with another dimension, or dependent on the selected target/stop/cost assumptions.

## Limitations

- Proxy backtest: it approximates historical consumer signals from candle-only features.
- No intraday sequence: daily candles do not reveal whether target or stop was hit first inside the same candle; the simulation is conservative.
- Simplified costs: commission and slippage are flat bps inputs.
- Survivorship bias: the current instrument universe may not match the historical investable universe.
- Small sample risk: narrow buckets can look strong or weak by chance.
- News and macro replay are limited in the proxy path, so those buckets are often `none` or `unknown`.
- This is not investment advice.

## Curl Examples

Quick run:

```bash
curl "http://127.0.0.1:8010/signals/consumer/expectancy-breakdown?max_tickers=10&max_samples=300"
```

With costs:

```bash
curl "http://127.0.0.1:8010/signals/consumer/expectancy-breakdown?max_tickers=10&max_samples=300&commission_bps=10&slippage_bps=5"
```

Different target/stop:

```bash
curl "http://127.0.0.1:8010/signals/consumer/expectancy-breakdown?max_tickers=20&max_samples=800&target_pct=0.04&stop_pct=0.025&horizon=20"
```

HTML page:

```bash
open "http://127.0.0.1:8010/signals/consumer/expectancy-breakdown-page"
```
