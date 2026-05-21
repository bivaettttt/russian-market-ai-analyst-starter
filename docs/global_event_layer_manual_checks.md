# Global Event Layer Manual Checks

Эти проверки нужны для ручной валидации глобального macro/geopolitical слоя без внешних платных API.

## 1. Добавить тестовую геополитическую новость

```bash
curl -X POST "http://127.0.0.1:8000/analyze/news" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "США начали операцию против Ирана, нефть Brent резко выросла",
    "text": "Военная операция США против Ирана усилила риски вокруг Ормузского пролива. Цены на нефть Brent выросли. Инвесторы уходят в защитные активы.",
    "source": "manual_test",
    "url": "manual://geo-oil-test"
  }'
```

Проверить:

```bash
curl -s "http://127.0.0.1:8000/signals/consumer/LKOH.json"
curl -s "http://127.0.0.1:8000/signals/consumer/ROSN.json"
curl -s "http://127.0.0.1:8000/signals/consumer/AFLT.json"
curl -s "http://127.0.0.1:8000/signals/consumer/PLZL.json"
```

Ожидания:

- `LKOH`/`ROSN`: `forecast.global_event_adjustment_pct > 0`
- `AFLT`: `forecast.global_event_adjustment_pct < 0`
- `PLZL`: `forecast.global_event_adjustment_pct > 0` или нейтральная поддержка risk-off
- `forecast.global_event_tags` содержит `geopolitical_risk`, `oil_shock`, `risk_off`
- `forecast.global_news_assessment.events` содержит событие, `tags`, `score`, `reasons`

## 2. Проверить снижение ключевой ставки на SBER и OFZ

```bash
curl -X POST "http://127.0.0.1:8000/analyze/news" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "ЦБ снизил ключевую ставку",
    "text": "Банк России снизил ключевую ставку и дал сигнал о возможном дальнейшем смягчении ДКП. Доходности ОФЗ снизились, девелоперы и банки выросли.",
    "source": "manual_test",
    "url": "manual://rates-down-test"
  }'
```

Проверить:

```bash
curl -s "http://127.0.0.1:8000/signals/consumer/SBER.json"
curl -s "http://127.0.0.1:8000/signals/consumer/PIKK.json"
curl -s "http://127.0.0.1:8000/signals/consumer/SMLT.json"
```

Ожидания:

- `forecast.global_event_adjustment_pct` у `SBER` положительный и обычно около `+1 п.п.`
- `forecast.global_event_tags` содержит `rates_down`, `bonds_positive`, `rate_sensitive_positive`
- `forecast.global_event_reason` объясняет влияние ставки на сценарий

## 3. Проверить list response и UI

```bash
curl -s "http://127.0.0.1:8000/signals/consumer.json?limit=50&scenario=all"
curl -s "http://127.0.0.1:8000/signals/consumer/SBER.json"
curl -s "http://127.0.0.1:8000/signals"
```

Поля для проверки:

- `summary.global_event_counts.with_global_events`
- `summary.global_event_counts.positive_adjustment`
- `summary.global_event_counts.negative_adjustment`
- `summary.global_event_counts.neutral_adjustment`
- `summary.global_event_counts.top_tags`
- `rows[].ticker_news_adjustment_pct`
- `rows[].global_event_adjustment_pct`
- `rows[].global_news_assessment`
- `rows[].global_event_tags`
- `rows[].global_event_reason`
- `rows[].macro_regime_flags`

На странице `/signals` на карточке должен быть отдельный бейдж `Макро`, а в блоке `Почему?` при наличии глобальных событий должна отображаться секция `Глобальный фон`.
