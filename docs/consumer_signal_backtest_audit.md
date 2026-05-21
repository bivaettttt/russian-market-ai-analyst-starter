# Consumer Signal Backtest Audit

`/signals/consumer/backtest-audit` измеряет историческое качество consumer decision model в формате proxy-аудита по дневным свечам. Это evaluation/reporting layer, а не обучение ML и не новая торговая модель.

## Что измеряется

- hit rate по `action`: `buy`, `consider_buy`, `watch`, `avoid_*`
- forward return после исторического proxy-сигнала
- target/stop/timeout outcomes
- какие `blocked_by` чаще защищали от плохих входов
- какие audit confidence buckets показывали лучшую статистику
- какие слои `signal_audit.passed_layers` чаще совпадали с успешными outcomes
- near-miss и worst false positives examples

## Отличие от ML evaluation

ML evaluation проверяет качество ML probability как отдельной модели. Backtest audit проверяет итоговую consumer decision pipeline в proxy-режиме: technical proxy, risk layer, decision gate и signal audit против будущих дневных свечей.

## Proxy Historical Audit

Исторический audit использует только candle-only features. Он не пытается переиграть live endpoint на каждую дату и не восстанавливает будущие новости.

Response явно содержит:

- `mode = proxy_historical_consumer_audit`
- `limitations`
- `note`

Исторические `ml`, `ticker_news`, `global_macro` в этом режиме считаются недоступными или оцениваются отдельно от live-сигнала.

## Outcome Logic

Для каждой исторической точки:

- `target_price = close * (1 + target_pct)`
- `stop_price = close * (1 - stop_pct)`
- future window: `index+1 ... index+horizon`

Интерпретация:

- `target_hit`: future high достиг target раньше stop.
- `stop_hit`: future low достиг stop раньше target.
- если target и stop внутри одной дневной свечи, используется conservative mode: `stop_hit`.
- `timeout`: за horizon не достигнут ни target, ни stop.
- для timeout `success=true`, если итоговый `forward_return_pct > 0`.

## Как читать метрики

`target_hit_rate_pct` показывает долю samples, где target был достигнут в горизонте.

`stop_hit_rate_pct` показывает долю samples, где stop был достигнут.

`timeout_rate_pct` показывает долю нерешённых samples.

`avg_forward_return_pct` — средняя доходность от close сигнальной свечи до последней свечи горизонта или доступного future window.

`avg_mfe_pct` — средний максимум благоприятного движения.

`avg_mae_pct` — средний максимум неблагоприятного движения.

## By Action

`by_action` отвечает на вопрос: какие итоговые consumer actions исторически чаще попадали в target, stop или timeout.

Сравнивайте:

- `buy`/`consider_buy` против `watch`
- `avoid_*` против target hits: если у avoid много target hits, модель может быть слишком строгой.
- `watch_bad_rr` и `avoid_bad_rr`: показывает, реально ли RR-фильтр отсекал плохие outcomes.

## By Blocker

`by_blocker` показывает качество veto/filters:

- `downside_signal`
- `weak_rr`
- `invalid_target`
- `risk_limit`
- `low_probability`
- `none`

Если blocker часто даёт низкий `stop_hit_rate_pct` и слабый `target_hit_rate_pct`, он полезен. Если blocker часто пропускает target hits в `near_miss_examples`, его стоит пересмотреть.

## By Audit Confidence

`by_audit_confidence` помогает понять, не стала ли модель слишком строгой или слишком мягкой:

- `high`: ожидаемо должен иметь лучшую статистику.
- `medium`: рабочая зона watch/consider.
- `low`: зона слабых сигналов и отказов.

## By Layer Support

`by_layer_support` агрегирует samples, где слой был в `signal_audit.passed_layers`.

В proxy historical audit чаще всего доступны:

- `technical`
- `risk`
- `scenario`

`ml`, `ticker_news`, `global_macro` могут отсутствовать, потому что исторический replay этих слоёв не выполняется.

## Curl

Быстрый прогон:

```bash
curl -s "http://127.0.0.1:8000/signals/consumer/backtest-audit?max_tickers=10&max_samples=200"
```

Более полный прогон:

```bash
curl -s "http://127.0.0.1:8000/signals/consumer/backtest-audit?max_tickers=100&max_samples=5000"
```

Страница отчёта:

```bash
curl -s "http://127.0.0.1:8000/signals/consumer/backtest-audit-page"
```

## Что нельзя считать доказательством

- Нет учёта проскальзывания.
- Нет комиссий и налогов.
- Нет intraday order внутри дневной свечи.
- Если target и stop задеты в одной свечи, audit консервативно считает stop.
- News/global events исторически не replay-ятся в proxy режиме.
- Возможен survivorship bias, если используется текущий instrument universe.
- Proxy candle-only action не обязан полностью совпадать с live consumer endpoint.
