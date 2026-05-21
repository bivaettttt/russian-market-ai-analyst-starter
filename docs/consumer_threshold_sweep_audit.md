# Consumer Threshold Sweep Audit

Threshold sweep audit — это исторический перебор параметров consumer-модели поверх proxy backtest audit. Он помогает увидеть, какие пороги дают лучшую статистику на истории, но не меняет production decision logic автоматически.

## Зачем нужен sweep

Обычный backtest audit отвечает: как текущая proxy consumer pipeline работала на истории.

Threshold sweep отвечает: как меняется качество, если перебрать параметры:

- `horizon`
- `target_pct`
- `stop_pct`
- `min_probability`
- `min_ml_probability`
- `min_rr`

Результат — ranked table:

```text
config | signals | target_hit_rate | stop_hit_rate | avg_forward_return | coverage | score
```

## Чем отличается от backtest audit

Backtest audit строит один historical report для заданного `horizon/target/stop`.

Threshold sweep строит набор proxy samples для разных `horizon/target/stop`, затем применяет разные threshold filters и ранжирует конфигурации по `calibration_score`.

Это calibration/evaluation layer, а не ML training.

## Параметры

- `horizon`: число будущих торговых дней для outcome.
- `target_pct`: целевое движение от close сигнальной свечи.
- `stop_pct`: stop distance от close сигнальной свечи.
- `min_probability`: минимальная proxy consumer probability.
- `min_ml_probability`: в proxy audit исторический ML не replay-ится, поэтому используется proxy probability. Это явно указано в warnings/limitations.
- `min_rr`: минимальный risk/reward.

## Score

`score` — эвристическая оценка качества конфигурации:

- растёт от `target_hit_rate_pct`
- растёт от положительного `avg_forward_return_pct`
- снижается от `stop_hit_rate_pct`
- снижается от `timeout_rate_pct`
- штрафует малое число signals
- даёт небольшой bonus за устойчивое число signals

Score ограничен диапазоном примерно `-100..100`.

## Quality Label

- `good`: `score >= 30` и `signals >= min_signals`
- `medium`: `score >= 10` и `signals >= min_signals`
- `weak`: `signals >= min_signals`, но `score < 10`
- `unstable`: `signals < min_signals`

## Почему best config нельзя применять автоматически

Лучший config — это диагностический кандидат, а не production rule. Перед применением нужно проверить:

- устойчивость на других периодах;
- чувствительность к universe;
- комиссии/проскальзывание;
- секторные перекосы;
- поведение на кризисных участках;
- соответствие risk policy.

## Ограничения

- Используется proxy backtest, а не полный replay live consumer endpoint.
- Нет комиссий, налогов, спредов и проскальзывания.
- Нет intraday order внутри дневной свечи.
- Если target и stop задеты в одной свече, считается `stop_hit`.
- News/global events исторически не replay-ятся.
- `min_ml_probability` использует proxy probability, потому что исторический ML replay недоступен.
- Возможен survivorship bias из-за текущего instrument universe.

## Curl Examples

Quick:

```bash
curl -s "http://127.0.0.1:8000/signals/consumer/threshold-sweep?max_tickers=10&max_samples=200&max_configs=40"
```

Medium:

```bash
curl -s "http://127.0.0.1:8000/signals/consumer/threshold-sweep?max_tickers=40&max_samples=1500&max_configs=120"
```

Custom grid:

```bash
curl -s "http://127.0.0.1:8000/signals/consumer/threshold-sweep?max_tickers=30&max_samples=1000&horizons=20,30&target_pcts=0.04,0.05&stop_pcts=0.03&min_probabilities=50,55,60&min_ml_probabilities=20,30&min_rr_values=1.0,1.2"
```

HTML page:

```bash
curl -s "http://127.0.0.1:8000/signals/consumer/threshold-sweep-page"
```
