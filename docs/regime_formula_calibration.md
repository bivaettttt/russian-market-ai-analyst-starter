# Regime Formula Calibration

Regime formula calibration — исследовательский threshold sweep для формулы `market_regime`. Он перебирает параметры классификации `risk_on / neutral / risk_off` и проверяет, улучшается ли proxy historical outcome после фильтрации long-сигналов в сильном risk-off.

Важно: найденный best config не применяется автоматически в production logic.

## Чем Отличается От Regime Historical Evaluation

`regime-historical-evaluation` проверяет текущую формулу режима на истории.

`regime-formula-calibration` перебирает альтернативные параметры формулы и сравнивает:

- baseline long samples;
- filtered samples после risk-off фильтра;
- delta по stop-hit, target-hit, average return и coverage.

## Перебираемые Параметры

- `risk_off_threshold` — порог перехода в `risk_off`;
- `strong_risk_off_threshold` — порог запрета long;
- `downside_pressure_block_threshold` — блокировка long при сильном downside pressure;
- `risk_off_position_multiplier` — диагностический multiplier для risk-off;
- `neutral_position_multiplier` — диагностический multiplier для neutral;
- `downside_weight` — вес downside pressure в score;
- `volatility_weight` — вес volatility pressure в score.

Остальные параметры берутся из совместимого default-конфига live formula.

## Как Читать Метрики

- `stop_hit_delta_pct`: `filtered_stop_hit_rate - baseline_stop_hit_rate`. Отрицательное значение хорошо: stop-hit снизился.
- `avg_return_delta_pct`: `filtered_avg_return - baseline_avg_return`. Положительное значение хорошо.
- `target_hit_delta_pct`: изменение target-hit. Сильное падение означает, что фильтр вырезал слишком много хороших входов.
- `avoided_stop_hits`: сколько stop-hit samples было отфильтровано.
- `missed_target_hits`: сколько target-hit samples было отфильтровано.
- `coverage_after_filter_pct`: доля сигналов, оставшаяся после фильтра.
- `score`: research score, который награждает снижение stop-hit и рост return, но штрафует потерю coverage и missed targets.
- `quality_label`: `good`, `medium`, `weak`, `unstable`.

## Почему Best Config Не Применяется Автоматически

Это proxy backtest, а не production validation. Даже хороший config может быть переоптимизирован под текущий universe, период и candle-only outcomes. Перед применением нужны walk-forward, sector buckets, paper trading и проверка на сохранённых real signal snapshots.

## Ограничения

- Proxy backtest не равен полному replay live consumer endpoint.
- Нет комиссий, налогов, спредов и проскальзывания.
- Дневные свечи не дают порядок high/low внутри дня.
- Возможен survivorship bias из-за текущего instrument universe.
- News/global historical context приближённый.
- Endpoint не меняет production thresholds.

## Curl Examples

Quick:

```bash
curl "http://127.0.0.1:8010/signals/consumer/regime-formula-calibration?max_tickers=10&max_samples=300&max_configs=30"
```

Medium:

```bash
curl "http://127.0.0.1:8010/signals/consumer/regime-formula-calibration?max_tickers=60&max_samples=2000&max_configs=80&min_signals_after_filter=30"
```

UI:

```bash
open "http://127.0.0.1:8010/signals/consumer/regime-formula-calibration-page"
```
