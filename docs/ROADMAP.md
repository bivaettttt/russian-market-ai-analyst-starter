# Roadmap

Текущий статус: Research Alpha+ / Validation Engine.

Оценка готовности:

- до аналитического MVP: 75-80%;
- до production-продукта: 60-65%.

## 1. Stabilization / Cleanup

Цель: сделать проект проще запускать, тестировать и сопровождать без изменения бизнес-логики сигналов.

Что сделать:

- нормальный запуск `pytest` из корня проекта;
- убрать warnings компиляции;
- расширить smoke-test под новые endpoints;
- добавить contract tests для критичных форматов ответа;
- актуализировать README и stabilization notes.

Acceptance criteria:

- `python3 -m pytest -q` работает без `PYTHONPATH`;
- `python3 -m compileall -q backend/app` проходит;
- smoke-test покрывает consumer validation endpoints;
- документация отражает текущий статус.

Почему важно: перед следующими исследовательскими этапами нужна стабильная базовая проверка, иначе сложно отличить regression от нормального изменения модели.

## 2. Regime-Aware Historical Evaluation

Цель: проверить, улучшает ли market regime filter историческое качество сигналов.

Что сделать:

- replay/proxy market regime по историческим датам;
- сравнить metrics с `use_market_regime_filter=false/true`;
- добавить breakdown по `risk_on`, `neutral`, `risk_off`;
- оценить, снижает ли regime filter stop-hit rate и false positives.

Acceptance criteria:

- backtest/threshold/walk-forward показывают metrics by regime;
- отчёт объясняет, где regime filter помогает, а где режет coverage без улучшения качества;
- результаты не применяются автоматически в production.

Почему важно: текущий walk-forward показывает слабую устойчивость порогов, и market regime должен быть проверен как risk-control слой, а не принят на веру.

## 3. Target / Stop / RR Calibration

Цель: откалибровать target, stop и RR thresholds по истории.

Что сделать:

- расширить grid по `target_pct`, `stop_pct`, `min_rr`;
- добавить buckets по волатильности и секторам;
- оценить trade-off hit rate, stop-hit, coverage и avg return;
- найти conservative defaults для consumer UI.

Acceptance criteria:

- threshold sweep показывает стабильные зоны параметров, а не один случайный best config;
- walk-forward подтверждает хотя бы умеренную устойчивость;
- документация фиксирует выбранные параметры и ограничения.

Почему важно: высокий stop-hit rate часто связан не только с probability threshold, но и с плохо подобранным target/stop контуром.

## 4. ML v2 / Model Quality Upgrade

Цель: улучшить ML probability layer без подмены explainable risk logic.

Что сделать:

- пересмотреть признаки и train/test split;
- добавить regime-aware features;
- сравнить lift по probability buckets;
- валидировать ML-veto отдельно от rule-based signal.

Acceptance criteria:

- ML evaluation показывает стабильный lift out-of-sample;
- ML-veto снижает bad entries без чрезмерного coverage loss;
- модель сохраняет diagnostics/reasons.

Почему важно: ML слой должен быть фильтром качества, а не источником непрозрачной рекомендации.

## 5. Production News Pipeline

Цель: заменить ручной/локальный news ingestion более надёжным pipeline.

Что сделать:

- регулярная загрузка событий из разрешённых источников;
- дедупликация и нормализация событий;
- оценка reliability/source quality;
- историческое хранение для validation.

Acceptance criteria:

- `/analyze/news` остаётся manual/dev входом;
- есть repeatable pipeline для ticker/global events;
- events можно использовать в historical audit без грубого look-ahead.

Почему важно: news и macro layers полезны только если события имеют понятное время, источник и надёжность.

## 6. Signal History / Paper Trading

Цель: перейти от proxy backtest к сохранению реальных daily consumer signals.

Что сделать:

- сохранять signal snapshots по расписанию;
- фиксировать forecast, audit, regime, news context;
- считать paper outcomes через 5/10/20/30 дней;
- строить dashboard drift/quality.

Acceptance criteria:

- есть таблица истории сигналов;
- можно проверить, какие реальные UI-сигналы сработали;
- paper-trading отчёт отделён от proxy historical audit.

Почему важно: это снижает риск look-ahead и показывает качество именно того сигнала, который видел пользователь.

## 7. Portfolio Risk Office

Цель: поднять уровень от отдельных сигналов до портфельного risk control.

Что сделать:

- sector/correlation exposure;
- max position and concentration limits;
- portfolio drawdown proxy;
- stress scenarios: sanctions, oil shock, FX shock, rates up/down.

Acceptance criteria:

- portfolio constructor показывает risk office diagnostics;
- отдельный хороший сигнал может быть ограничен портфельными лимитами;
- risk reasons понятны в UI.

Почему важно: инвестиционное решение зависит не только от тикера, но и от уже существующего портфеля.

## 8. Production Layer

Цель: подготовить систему к безопасной эксплуатации.

Что сделать:

- deployment config;
- auth/access control;
- monitoring and alerts;
- migrations and backups;
- legal disclaimers and audit logs;
- rate limits for heavy validation endpoints.

Acceptance criteria:

- сервис можно развернуть воспроизводимо;
- heavy endpoints ограничены;
- есть наблюдаемость, логи и rollback план;
- юридический статус продукта описан явно.

Почему важно: research engine не должен превращаться в production-продукт без контроля безопасности, доступов и ответственности.
