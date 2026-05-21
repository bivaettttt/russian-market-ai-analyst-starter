# Trade Outcome PnL Simulation

Trade outcome PnL simulation добавляет реализованный результат сделки к proxy validation endpoints.

Раньше отчёты показывали `target_hit`, `stop_hit`, `timeout` и `forward_return_pct`. Это полезно, но может конфликтовать с реальной логикой сделки: если target достигнут раньше horizon, сделка должна фиксировать `+target_pct`, а не доходность на последней свече.

## Правила

- `target_hit` → `trade_return_pct = target_return_pct - costs`
- `stop_hit` → `trade_return_pct = stop_return_pct - costs`
- `timeout` → `trade_return_pct = forward_return_pct - costs`
- если target и stop задеты в одной дневной свече, используется conservative mode: `stop_hit`

`cost_pct = (commission_bps + slippage_bps) / 100`.

Пример: `commission_bps=10` и `slippage_bps=5` дают cost `0.15%`.

## Forward Return vs Trade Return

- `forward_return_pct`: доходность от entry close до последнего close в горизонте.
- `trade_return_pct`: реализованный результат по правилам target/stop/timeout.
- `target_hit_rate_pct` и `stop_hit_rate_pct`: структура outcomes, но не сумма PnL.

## Метрики

- `avg_trade_return_pct`: средний реализованный результат сделки.
- `median_trade_return_pct`: медианный реализованный результат.
- `total_trade_return_pct`: сумма trade returns без compounding.
- `win_rate_pct`: доля сделок с `trade_return_pct > 0`.
- `loss_rate_pct`: доля сделок с `trade_return_pct < 0`.
- `profit_factor`: сумма wins / abs(сумма losses).
- `expectancy_pct`: то же, что средний trade return.
- `payoff_ratio`: average win / abs(average loss).
- `avg_win_pct`: средний выигрыш.
- `avg_loss_pct`: средний убыток.
- `max_trade_loss_pct`: худший trade return.

## Ограничения

- Нет intraday sequence внутри дневной свечи.
- Same-candle target/stop считается консервативно как stop.
- Commission/slippage заданы упрощённо в bps.
- Нет реалистичного order book/liquidity fill.
- Это proxy backtest, не инвестиционная рекомендация.

## Curl Examples

Adaptive calibration:

```bash
curl "http://127.0.0.1:8010/signals/consumer/adaptive-trade-calibration?max_tickers=10&max_samples=300&max_policies=30"
```

Adaptive calibration with costs:

```bash
curl "http://127.0.0.1:8010/signals/consumer/adaptive-trade-calibration?max_tickers=10&max_samples=300&max_policies=30&commission_bps=10&slippage_bps=5"
```

Backtest with costs:

```bash
curl "http://127.0.0.1:8010/signals/consumer/backtest-audit?max_tickers=10&max_samples=200&commission_bps=10&slippage_bps=5"
```
