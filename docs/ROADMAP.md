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

Статус: реализовано в первом proxy-варианте; quick evaluation показал, что текущий risk-off filter полезен как диагностика, но пока не даёт сильного снижения stop-hit.

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

## 3. Regime Formula Calibration

Статус: реализовано как research endpoint. Quick result: best quality пока weak, recommendation `recalibrate_needed`; production thresholds не менялись.

Цель: откалибровать формулу `risk_on / neutral / risk_off` отдельно от production logic.

Что сделать:

- перебрать thresholds `risk_off`, `strong_risk_off`, `downside_pressure`;
- проверить разные веса downside и volatility;
- сравнить baseline vs filtered outcomes;
- оценить missed target hits и coverage loss;
- оставить best configs как research output без автоматического применения.

Acceptance criteria:

- endpoint calibration возвращает ranked configs;
- score учитывает снижение stop-hit, рост return, missed targets и coverage;
- UI показывает best configs и limitations;
- документация явно говорит, что config не применяется в production автоматически.

Почему важно: если regime filter не снижает stop-hit на текущих порогах, нужно калибровать саму формулу, а не усиливать production gate вручную.

## 4. Adaptive Target / Stop / RR Calibration

Статус: реализовано как research endpoint. Quick result показал, что ATR policy меняет hit structure, но forward return может конфликтовать с target/stop outcome.

Цель: откалибровать конструкцию сделки: target, stop, horizon и min RR по истории.

Что сделать:

- сравнить fixed `5% / 3% / 20` с ATR-based и volatility-scaled policies;
- добавить liquidity/volatility/sector-aware placeholders;
- оценить trade-off target-hit, stop-hit, coverage, MFE/MAE и avg return;
- найти кандидаты для последующей walk-forward/paper validation.

Acceptance criteria:

- adaptive calibration возвращает ranked policies;
- baseline fixed policy явно присутствует в summary;
- best policy не применяется автоматически в production;
- документация фиксирует ограничения proxy evaluation.

Почему важно: высокий stop-hit rate часто связан не только с probability threshold, но и с плохо подобранным target/stop контуром.

## 5. Trade Outcome PnL Simulation

Статус: реализовано. Quick result с costs 10 bps + 5 bps показал отрицательную expectancy, поэтому следующий шаг — диагностика сегментов.

Цель: считать реализованный PnL сделки, а не только `forward_return_pct`.

Что сделать:

- target_hit считать как `+target_pct`;
- stop_hit считать как `-stop_pct`;
- timeout считать по forward return;
- добавить bps costs;
- протащить PnL metrics в backtest, sweep, walk-forward, regime reports.

Acceptance criteria:

- отчёты содержат `avg_trade_return_pct`, `profit_factor`, `expectancy_pct`, `payoff_ratio`, `win_rate_pct`;
- endpoints с `commission_bps/slippage_bps` работают;
- production decision logic не меняется.

Почему важно: hit-rate без реализованного PnL может давать неверный вывод о качестве trade setup.

## 6. Expectancy Breakdown Diagnostics

Статус: реализовано как research endpoint/page. На текущей локальной базе quick run показал `samples=0`, поэтому следующий шаг — диагностика покрытия данных.

Цель: найти, по каким сегментам модель уже имеет положительную expectancy, а по каким стабильно теряет.

Что сделать:

- разбить trade PnL по action, ticker, sector, asset_type, volatility/liquidity buckets, market regime, probability buckets, RR, audit confidence, blockers, news/macro effects;
- выделить positive pockets и negative pockets;
- сформировать candidate filters и candidate boosts как research recommendations;
- не менять production decision logic автоматически.

Acceptance criteria:

- endpoint возвращает summary, dimensions, positive_pockets, negative_pockets, candidate_filters и candidate_boosts;
- страница открывает breakdown и показывает таблицы по dimensions;
- маленькие buckets помечаются как unstable;
- pytest и smoke-test проходят.

Почему важно: общая отрицательная expectancy может быть смесью хороших и плохих сегментов. Перед изменением thresholds нужно понять, что именно портит общий результат.

## 7. Data Coverage Diagnostics

Статус: реализовано. Локальная диагностика показала `empty_database`, поэтому следующий blocker — воспроизводимо заполнить БД инструментами и свечами.

Цель: понять, почему historical validation endpoints могут возвращать `0 samples`.

Что сделать:

- посчитать instruments, eligible universe, asset_type mapping и candle coverage;
- показать usable tickers и possible historical samples для текущих `min_history/horizon`;
- выделить skip reasons: no_candles, too_few_candles, insufficient_horizon, invalid_ohlc, not_signal_eligible, unsupported_asset_type;
- дать рекомендации по догрузке свечей или диагностическому снижению параметров.

Acceptance criteria:

- `/signals/data-coverage` возвращает summary, skip_reasons, examples и recommendations;
- `/signals/data-coverage-page` открывается и работает при пустой базе;
- empty-sample endpoints явно отправляют к Data coverage diagnostics;
- production decision logic не меняется.

Почему важно: калибровка expectancy, thresholds и target/stop бессмысленна, пока не понятно, есть ли достаточное историческое покрытие свечей.

## 8. Local MOEX Data Bootstrap

Статус: реализовано. После bootstrap data coverage стал `good`, появились usable historical samples для validation endpoints.

Цель: сделать воспроизводимый локальный bootstrap для MOEX universe и дневных свечей.

Что сделать:

- загрузить instruments из публичных MOEX ISS endpoints;
- upsert в локальную таблицу `instruments` с `asset_type` и `is_signal_eligible`;
- загрузить дневные candles по eligible tickers с лимитами, timeout, retry и pause;
- добавить CLI dry-run/full bootstrap;
- проверять результат через Data Coverage Diagnostics.

Acceptance criteria:

- команда `python3 -m app.tasks.bootstrap_market_data --dry-run --max-tickers 3 --days 30` работает без записи в БД;
- маленький bootstrap может загрузить несколько тикеров;
- после загрузки `/signals/data-coverage` показывает usable samples;
- runtime DB files не коммитятся.

Почему важно: validation engine не может калибровать expectancy и thresholds без локального исторического покрытия.

## 9. Candidate Filter Calibration

Статус: реализовано. Quick result: одиночные ticker/bucket filters дали только weak improvement, поэтому следующий шаг — composite decision rules.

Цель: проверить, улучшают ли простые фильтры по negative/positive pockets expectancy без разрушения coverage.

Что сделать:

- использовать pockets из expectancy breakdown;
- проверить single exclude/include filters и простые combo filters;
- оценить avg trade return, profit factor, win rate, stop-hit, avoided losses, missed wins и coverage;
- оставить результаты как research output без автоматического применения в production.

Acceptance criteria:

- endpoint возвращает ranked filters и baseline/filtered/removed metrics;
- UI показывает best filters, deltas, warnings и limitations;
- фильтры с малой выборкой помечаются unstable;
- production decision logic не меняется.

Почему важно: adaptive target/stop почти вывел expectancy в ноль, но нужен отдельный слой проверки, какие отрицательные сегменты портят результат.

## 10. Composite Decision Rule Calibration

Статус: реализовано. Quick result: best rule остался weak, recommendation `no_material_rule`; простые composite conditions не нашли устойчивого edge.

Цель: проверить комбинации условий входа, а не одиночные filters.

Что сделать:

- сгенерировать bounded grid composite rules по probability, RR, ML proxy, market regime, volatility, liquidity, audit confidence, news/macro;
- оценить selected samples vs baseline по avg trade return, profit factor, win rate, stop-hit и coverage;
- помечать tiny-coverage rules как unstable;
- не применять найденные правила автоматически в production.

Acceptance criteria:

- endpoint возвращает ranked composite rules;
- UI показывает summary, best rules, conditions, warnings и limitations;
- score penalizes low coverage and overfitting risk;
- следующий шаг — walk-forward validation лучших rule candidates.

Почему важно: single filters не дали material improvement, а входное качество может зависеть от сочетания probability + RR + regime + liquidity.

## 11. Target / Stop / RR Calibration Follow-Up

Цель: проверить лучшие adaptive policies на устойчивость.

Что сделать:

- walk-forward по policy candidates;
- sector/liquidity/volatility buckets;
- compare against real signal snapshots when available;
- conservative defaults only after validation.

Acceptance criteria:

- выбран не один best config, а стабильная зона параметров;
- результат не ухудшает coverage без улучшения risk metrics;
- есть paper-trading план применения.

Почему важно: хороший single-sample policy может быть случайной подгонкой.

## 12. ML v2 / Model Quality Upgrade

Статус: реализовано как research layer. Quick result: общий AUC слабый, но high-confidence threshold 60% дал небольшой positive PnL pocket, поэтому нужен rolling validation.

Цель: улучшить ML probability layer без подмены explainable risk logic.

Что сделать:

- пересмотреть признаки и train/test split;
- перейти от одного target-before-stop label к trade PnL labels: positive return, avoid stop, good trade;
- добавить PnL-aware threshold report;
- добавить regime-aware features;
- сравнить lift по probability buckets;
- валидировать ML-veto отдельно от rule-based signal.

Acceptance criteria:

- ML evaluation показывает стабильный lift out-of-sample;
- ML-veto снижает bad entries без чрезмерного coverage loss;
- модель сохраняет diagnostics/reasons.

Почему важно: ML слой должен быть фильтром качества, а не источником непрозрачной рекомендации.

## 13. ML v2 High-Confidence Validation

Статус: реализовано. Quick result: threshold 55% получил stable quality и recommendation `use_as_research_gate`.

Цель: проверить, устойчив ли ML v2 high-confidence bucket на walk-forward splits.

Что сделать:

- обучать ML v2 на expanding train windows;
- проверять thresholds 50/55/60/65/70% на forward test windows;
- агрегировать PnL, profit factor, coverage и stable positive folds;
- не применять threshold автоматически в production.

Acceptance criteria:

- endpoint возвращает fold reports и threshold summary;
- high-confidence thresholds получают quality_label и recommendation;
- low-sample thresholds помечаются unstable;
- результаты требуют paper trading validation.

Почему важно: слабый общий AUC не исключает маленький полезный high-confidence bucket, но его нужно проверить на устойчивость во времени.

## 14. ML v2 Research Gate Integration

Статус: текущий этап.

Цель: подключить ML v2 high-confidence result как diagnostic-only layer в consumer signals.

Что сделать:

- добавить query flag `use_ml_v2_research_gate`;
- показывать `ml_v2_probability_pct`, threshold, status, reason и research note;
- добавить `signal_audit.layer_scores.ml_v2_research_gate`;
- не менять production action/recommendation по умолчанию;
- graceful fallback, если ML v2 artifact отсутствует.

Acceptance criteria:

- `/signals/consumer/SBER.json` работает без ML v2 artifact;
- `/signals/consumer/SBER.json?use_ml_v2_research_gate=true` возвращает status `passed/rejected/not_available/error`;
- список сигналов и UI показывают ML v2 badge только как research diagnostic;
- ML v1 остаётся production ML layer.

Почему важно: high-confidence bucket показал research edge, но его нужно сначала наблюдать в текущих consumer signals без автоматического veto.

## 15. Production News Pipeline

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

## 16. Signal History / Paper Trading

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

## 17. Portfolio Risk Office

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

## 17. Production Layer

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
