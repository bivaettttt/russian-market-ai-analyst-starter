# Adaptive Target / Stop / RR Calibration

Adaptive trade calibration сравнивает фиксированную схему сделки `target=5%`, `stop=3%`, `horizon=20` с альтернативными target/stop policies на proxy historical samples.

Это research/calibration layer. Best policy не применяется автоматически в production consumer logic.

## Зачем Это Нужно

Если stop-hit высокий, проблема может быть не только в probability threshold или regime filter. Часто фиксированный target/stop не подходит для разных волатильностей, ликвидности и рыночных режимов:

- для спокойных бумаг target 5% может быть слишком далёким;
- для высоковолатильных бумаг stop 3% может быть слишком узким;
- одинаковый horizon может плохо работать для разных setup types;
- min RR может отсеивать или пропускать неправильные сделки.

## Policy Types

- `fixed_pct`: фиксированные target/stop/horizon, включая baseline `5% / 3% / 20`.
- `atr_multiple`: target и stop считаются как multiples от ATR.
- `volatility_scaled`: target и stop масштабируются от realized volatility с min/max clamps.
- `conservative_liquid`: bucket-aware placeholder для ликвидных бумаг с более коротким horizon.
- `high_volatility_wide_stop`: bucket-aware placeholder для высоковолатильных бумаг с wider stop.

## Как Читать Метрики

- `target_hit_rate_pct`: доля samples, где target был достигнут раньше stop.
- `stop_hit_rate_pct`: доля samples, где stop был достигнут раньше target.
- `avg_forward_return_pct`: средняя forward доходность на horizon policy.
- `median_forward_return_pct`: медианная forward доходность.
- `avg_mfe_pct`: средний максимум favorable excursion.
- `avg_mae_pct`: средний максимум adverse excursion, обычно отрицательный.
- `avg_target_pct`: средний рассчитанный target.
- `avg_stop_pct`: средний рассчитанный stop.
- `avg_rr`: средний risk/reward.
- `rejected_by_min_rr`: сколько samples не прошло min RR policy.
- `score`: research score, который награждает target-hit/return/MFE и штрафует stop-hit/timeout/MAE/низкую coverage.
- `quality_label`: `good`, `medium`, `weak`, `unstable`.

## Почему Best Policy Не Применяется Автоматически

Policy может быть переоптимизирована под текущий universe и исторический период. Перед production нужно проверить:

- walk-forward;
- sector/volatility/liquidity buckets;
- paper trading на сохранённых real signal snapshots;
- влияние на actual consumer recommendations и position sizing.

## Ограничения

- Proxy evaluation не равен полному replay live consumer endpoint.
- Нет комиссий, налогов, спредов и проскальзывания.
- Дневные свечи не дают порядок high/low внутри дня.
- Текущий universe может давать survivorship bias.
- Adaptive policy grid может переобучиться на sample.
- News, global macro и ML probability исторически не replayed в этом слое.

## Curl Examples

Quick:

```bash
curl "http://127.0.0.1:8010/signals/consumer/adaptive-trade-calibration?max_tickers=10&max_samples=300&max_policies=30"
```

Medium:

```bash
curl "http://127.0.0.1:8010/signals/consumer/adaptive-trade-calibration?max_tickers=60&max_samples=2000&max_policies=80&min_samples_per_policy=30"
```

UI:

```bash
open "http://127.0.0.1:8010/signals/consumer/adaptive-trade-calibration-page"
```
