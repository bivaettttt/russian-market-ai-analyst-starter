# Signal Audit Layer

`signal_audit` — это объяснимый audit поверх уже существующего consumer signal. Он не является новой торговой моделью и не меняет `action`, `recommendation` или `target_probability_pct`. Его задача — показать, какие слои поддержали итоговое решение, какие слои предупредили или заблокировали вход, и что должно улучшиться для upgrade сигнала.

## Score Meaning

`overall_score` — оценка качества итогового решения, а не вероятность роста.

Пример: у `avoid` или `downside_risk` score может быть средним, если система уверенно объясняет отказ от покупки. Для вероятности достижения цели нужно смотреть `target_probability_pct`.

## Слои

- `technical`: rule/technical слой, исходный action, цель относительно текущей цены, rule probability.
- `ml`: ML probability, ML adjustment, вес ML и режимный множитель.
- `risk`: position sizing, risk/reward, stop/target distance, разрешение позиции.
- `ticker_news`: локальные новости по тикеру, relevance, effect и news adjustment.
- `global_macro`: глобальный macro/geopolitical фон, tags, adjustment и reason.
- `scenario`: long/neutral/downside классификация исходного сценария.

Каждый слой содержит:

- `status`: `positive`, `neutral`, `negative`, `not_available`
- `score`: 0–100 или `null`
- `reason`: короткое объяснение по-русски
- `diagnostics`: компактные исходные признаки слоя

## blocked_by

`blocked_by` показывает причины, которые ограничили или запретили покупку:

- `ml_veto`: ML probability ниже критического порога.
- `weak_rr`: risk/reward слабее минимального порога.
- `invalid_target`: цель для long не выше текущей цены.
- `downside_signal`: исходный сценарий downside/risk.
- `risk_limit`: риск-слой не разрешил вход.
- `ticker_news_veto`: сильный негативный ticker news veto.
- `low_probability`: итоговая вероятность ниже потребительского порога.

## Примеры

### SBER: macro supports, final watch

При снижении ключевой ставки `global_macro` может быть `positive`: tags вроде `rates_down`, `bonds_positive`, `rate_sensitive_positive`, adjustment около `+1 п.п.`. Итог при этом может оставаться `watch`, если технический слой, ML или risk/reward не дают достаточного подтверждения для `consider_buy`.

Смотреть:

```bash
curl -s "http://127.0.0.1:8000/signals/consumer/SBER.json"
```

Поля:

- `forecast.signal_audit.final_verdict`
- `forecast.signal_audit.layer_scores.global_macro`
- `forecast.signal_audit.human_explanation`
- `forecast.global_event_adjustment_pct`

### AFLT: downside/risk

Если исходный сценарий downside или цель ниже текущей цены, audit должен показать `final_verdict=downside_risk` или `avoid`, а `blocked_by` должен содержать `downside_signal`.

```bash
curl -s "http://127.0.0.1:8000/signals/consumer/AFLT.json"
```

Поля:

- `forecast.scenario_direction`
- `forecast.signal_audit.blocked_by`
- `forecast.signal_audit.layer_scores.scenario`
- `forecast.signal_audit.risk_committee_note`

### weak_rr

Если вероятность приемлемая, но `risk_reward_ratio < 1.2`, audit помечает risk layer как warning/negative и добавляет `weak_rr`.

Поля:

- `forecast.risk_reward_ratio`
- `forecast.position_sizing.target_distance_pct`
- `forecast.position_sizing.stop_distance_pct`
- `forecast.signal_audit.layer_scores.risk`

### ml_veto

Если `ml_probability_pct < 15`, audit добавляет `ml_veto`, ML layer становится negative, а итоговый сигнал не может быть покупкой.

Поля:

- `forecast.ml_probability_pct`
- `forecast.signal_audit.layer_scores.ml`
- `forecast.signal_audit.blocked_by`

## List Response

```bash
curl -s "http://127.0.0.1:8000/signals/consumer.json?limit=50&scenario=all"
```

Смотреть:

- `summary.audit_counts`
- `summary.audit_counts.blocked_by`
- `rows[].signal_audit`
- `rows[].audit_overall_score`
- `rows[].audit_confidence_level`
- `rows[].audit_blocked_by`
- `rows[].audit_top_strengths`
- `rows[].audit_top_weaknesses`

## UI

На странице `/signals` карточка показывает бейдж `Audit: score / confidence`. В блоке `Почему?` есть секция `Аудит сигнала` с human explanation, risk note, strengths/weaknesses, required improvements и компактными layer scores.
