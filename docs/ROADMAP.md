# Roadmap

Текущий статус: Research Alpha+ with Experimental ML Gate / Validation Engine.

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

Статус: реализовано. ML v2 gate подключён как diagnostic-only layer с safe fallback при отсутствии artifact.

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

## 15. ML v2 Gate Impact Evaluation

Статус: реализовано. Artifact-based impact показал сильный hard_gate 60%, но с caveat possible training leakage.

Цель: исторически сравнить diagnostic-only, soft downgrade и hard gate режимы ML v2 research gate.

Что сделать:

- использовать сохранённый ML v2 artifact для scoring historical samples;
- сравнить thresholds 50/55/60/65/70%;
- считать baseline vs selected PnL, profit factor, win-rate, stop-hit и coverage;
- считать avoided losses и missed wins;
- явно предупреждать о possible training leakage artifact-based evaluation;
- не менять production consumer logic.

Acceptance criteria:

- endpoint возвращает artifact_missing без падения, если artifact отсутствует;
- при наличии artifact возвращает ranked gate mode/threshold results;
- UI показывает best mode, threshold, deltas, warnings и limitations;
- результаты требуют walk-forward/paper validation перед production.

Почему важно: high-confidence validation показал research edge, но нужно понять impact на consumer-like decisions и цену coverage loss.

## 16. Leakage-safe ML v2 Gate Walk-forward

Статус: реализовано. Quick result: hard_gate 55% получил stable quality и recommendation `promising_gate`.

Цель: проверить ML v2 gate без training leakage через expanding train windows и future test windows.

Что сделать:

- строить ML v2 dataset и сортировать samples по date;
- на каждом fold обучать ML v2 только на train-period;
- применять diagnostic_only, soft_downgrade и hard_gate только на future test-period;
- агрегировать coverage, avg trade return, profit factor, stop-hit, positive folds и stability;
- не менять production consumer logic.

Acceptance criteria:

- endpoint возвращает fold reports и aggregate gate mode/threshold results;
- результаты не требуют сохранённого artifact;
- low-sample thresholds помечаются unstable;
- recommendation отделяет promising research gate от production readiness.

Почему важно: только leakage-safe walk-forward может подтвердить, что ML v2 gate действительно улучшает будущие consumer/trade outcomes.

## 17. Experimental ML v2 Decision Gate

Статус: реализовано как explicit experimental mode. Default consumer behavior не меняется.

Цель: подключить ML v2 gate как явно включаемый экспериментальный decision layer без изменения default production behavior.

Что сделать:

- добавить `ml_v2_gate_mode=diagnostic_only|soft_downgrade|hard_gate`;
- оставить default `diagnostic_only` и `use_ml_v2_research_gate=false`;
- в soft mode понижать rejected long candidates до `watch_ml_v2_rejected`;
- в hard mode отклонять rejected long candidates как `avoid_ml_v2_rejected`;
- сохранять original/final action, gate effect и research basis в forecast/audit/UI;
- добавить snapshot comparison endpoint baseline vs gated.

Acceptance criteria:

- существующие `/signals/consumer*.json` не меняют поведение без флага;
- artifact missing не ломает сигнал и не меняет action;
- UI показывает mode/effect и before/after action;
- compare endpoint показывает changed actions и ML v2 counts.

Почему важно: leakage-safe validation дала promising research gate, но внедрение должно оставаться контролируемым и обратимым.

## 18. Experimental ML v2 Gate Historical Backtest

Статус: реализовано как research endpoint/page для proxy consumer-сигналов. Leakage-safe consumer backtest дал recommendation `reject` для ML v2 gate на consumer distribution.

Цель: исторически проверить, улучшает ли experimental ML v2 decision gate именно consumer long candidates.

Что сделать:

- реконструировать historical/proxy consumer actions;
- считать leakage-safe ML v2 predictions без требования saved artifact;
- сравнить baseline, diagnostic_only, soft_downgrade и hard_gate;
- показать passed/rejected buckets, selected PnL, coverage, avoided losses и missed wins;
- оставить production default без изменений.

Acceptance criteria:

- endpoint `/signals/consumer/ml-v2-gate-backtest` возвращает ranked results;
- page `/signals/consumer/ml-v2-gate-backtest-page` показывает summary, таблицу и changed examples;
- artifact mode безопасно возвращает `ok=false` при missing artifact;
- документация фиксирует leakage, proxy action и candle-only limitations.

Почему важно: walk-forward подтвердил общий gate на trade dataset, но consumer decision layer требует отдельной исторической проверки перед paper trading.

## 19. Consumer Candidate ML v3 Dataset & Validation

Статус: реализовано как research layer. Результат на текущей DB: ML v3 не нашёл stable edge, recommendation `reject`.

Цель: обучать модель не на generic trade samples, а только на historical consumer long-candidates.

Что сделать:

- собрать dataset по `buy`, `consider_buy`, `watch_ml_confirmed` и legacy long actions;
- добавить consumer decision, technical, trade setup, regime и instrument features;
- обучить ML v3 time-split evaluation;
- проверить thresholds через leakage-safe walk-forward;
- сравнить baseline candidates, diagnostic buckets, soft_downgrade и hard_gate;
- не менять production consumer logic.

Acceptance criteria:

- endpoints dataset/evaluation/walk-forward возвращают JSON research reports;
- page `/signals/ml-v3/consumer-candidate/page` показывает summary, thresholds, folds и features;
- training task сохраняет локальный artifact без добавления его в git;
- результаты используются только для следующего research этапа experimental ML v3 gate.

Почему важно: ML v2 провалился как consumer decision gate из-за distribution mismatch; ML v3 проверяет именно ту выборку, которую реально создаёт consumer layer.

## 20. Consumer Candidate Generation Redesign / Setup Family Research

Статус: реализовано как setup family research layer. Research result: pure OHLCV setup families improved old consumer baseline but still found no stable positive long edge.

Цель: проверить альтернативные способы генерации long-candidates через прозрачные setup families до изменения production rules.

Что сделать:

- классифицировать historical candle samples по breakout, pullback, mean reversion, momentum, squeeze, trend и liquidity/quality setups;
- считать target/stop PnL по existing adaptive policy;
- сравнить setup families с old consumer candidates;
- выполнить bounded parameter sweep по ключевым thresholds;
- оставить результаты research-only.

Acceptance criteria:

- endpoints `/signals/setup-family/research` и `/signals/setup-family/sweep` возвращают ranked setup reports;
- page `/signals/setup-family/research-page` показывает family metrics, sweep configs, examples и limitations;
- tests покрывают setup classifier и quality/scoring helpers;
- production consumer recommendations не меняются.

Почему важно: если ML поверх candidates не помогает, нужно улучшать саму генерацию candidates и искать setup families с положительной expectancy.

## 21. Event-Aware Setup Research

Статус: реализовано как research layer. Research result: слой готов, но был заблокирован отсутствием исторического покрытия событий (`event_samples=0` при live-only events).

Цель: проверить, появляется ли edge, когда technical setup подтверждён event/news/macro catalyst.

Что сделано:

- добавлен deterministic mapping event category/tag → ticker/sector/market impact;
- добавлен coverage endpoint для локальной истории событий;
- добавлен research endpoint для сравнения setup-only, event-only, setup+event confirmation/conflict/neutral buckets;
- добавлен bounded sweep по lookback/decay/min event score/confirmation mode/setup mode;
- добавлена HTML-страница `/signals/event-aware/research-page`;
- production consumer recommendations не меняются.

Почему важно: предыдущий этап показал, что на текущих OHLCV/technical features устойчивого long-edge нет; следующий проверяемый источник edge — внешний catalyst.

## 22. Historical Event Data Bootstrap

Статус: реализовано как offline curated seed bootstrap. После импорта event-aware research начал возвращать non-zero event samples.

Цель: заполнить локальную `MarketEvent` историю, чтобы event-aware setup research мог сопоставлять candle samples с catalyst events.

Что сделано:

- добавлен seed `backend/app/data/seed/historical_events_seed.json` с curated macro/rates/fx/oil/dividend/sanctions markers за 2022-2026;
- добавлен idempotent import/upsert в существующую `MarketEvent`;
- добавлен dry-run CLI `python3 -m app.tasks.bootstrap_historical_events --dry-run`;
- добавлен read-only endpoint `/signals/events/bootstrap-status`;
- coverage diagnostics показывает source/year/family/direction и рекомендации.

Почему важно: без исторических событий event-aware layer не может отличить setup-only от setup+event candidates.

## 22.1 Historical Event Data Expansion v2

Статус: реализовано как расширение curated seed coverage.

Цель: сделать event-aware validation менее зависимой от редких seed events и дать walk-forward fold diagnostics больше событийных samples по годам.

Что сделано:

- seed расширен до 250+ событий за 2022-2026;
- добавлены `curated_seed_v2` macro/rates/inflation/FX/oil/commodities/sanctions/geopolitics/dividend/earnings/corporate/sector markers;
- bootstrap сохраняет source и возвращает `by_year` / `by_source`;
- coverage diagnostics показывает density, by-month, gaps и рекомендации;
- event-aware walk-forward показывает event/confirmed sample coverage by year/fold.

Следующий этап: rerun event-aware walk-forward на расширенной event history; если edge станет стабильным, проектировать Event-Aware Candidate Generator v1.

## 23. Event-Aware Walk-forward Validation

Статус: реализовано как leakage-safe validation layer. Research result после seed v2: `research_only`, потому что positive folds остаются `1/4`, а selected samples по fold слишком редкие.

Цель: проверить, не является ли лучший event/setup combo результатом overfit на одном событии, году, секторе или тикере.

Что сделано:

- train folds выбирают лучшие combos только на прошлом окне;
- test folds применяют выбранные combos только к будущим samples;
- результат сравнивается с all event-aware baseline, confirmed-only и setup-only buckets;
- добавлены concentration checks по ticker/event/year;
- добавлены endpoint `/signals/event-aware/walk-forward` и page `/signals/event-aware/walk-forward-page`.

Почему важно: статический PF на малой выборке не является достаточным основанием для нового candidate generator.

## 23.1 Event-Aware Generalized Rule Search

Статус: реализовано как research layer. Research result для long-only: `reject` на full walk-forward, несмотря на более широкий sample coverage.

Цель: заменить сверхузкие combo keys более широкими правилами, которые выбираются на train folds и проверяются на будущих test folds.

Что сделано:

- добавлен endpoint `/signals/event-aware/rule-search`;
- добавлена page `/signals/event-aware/rule-search-page`;
- добавлены rule families: confirmation, conflict/rebound, event group, setup group + event direction, score thresholds, broad coverage, filter style;
- selected test samples deduplicated by ticker/date/setup/event;
- добавлены concentration diagnostics и rule frequency.

Почему важно: если generalized rules дают `3/4` positive folds, PF >= `1.10`, положительную доходность и достаточный sample count, это станет основой Event-Aware Candidate Generator v1.

## 23.2 Dual-Side Event-Aware Outcome Research

Статус: реализовано как research layer для risk/avoid-long проверки. Static diagnostics promising, но walk-forward risk filter rejected: positive impact folds `0/4`, avg return/PF delta отрицательные.

Цель: проверить, полезен ли event-aware слой не как long-entry engine, а как downside watch / avoid-long / reduce-exposure filter.

Что сделано:

- добавлены endpoints `/signals/event-aware/dual-side-research` и `/signals/event-aware/dual-side-walk-forward`;
- добавлена page `/signals/event-aware/dual-side-page`;
- samples enrich с downside labels: stop-hit, negative return, downside flag, avoid benefit, missed upside;
- static research ранжирует `avoid_long`, `downside_watch`, `long_candidate` rules;
- walk-forward выбирает risk rules на train и применяет их как фильтр на future test.

Почему важно: отрицательный long-edge не означает, что event layer бесполезен; он может быть сильнее в роли risk filter.

## 23.3 Event-Aware Rule Stability Diagnostics

Статус: реализовано как diagnostics/research layer. Full diagnostics found stable-looking rules, but primary failure reason remains `winner_miss_rate`.

Цель: объяснить, почему static event risk rules не переносятся в walk-forward.

Что сделано:

- добавлен endpoint `/signals/event-aware/rule-stability`;
- добавлена page `/signals/event-aware/rule-stability-page`;
- stability metrics считаются by year, chronological bucket, market regime, event family, setup group;
- добавлена concentration диагностика по ticker/event/year/sector;
- failure analysis объясняет: rule instability, missed winners, concentration, regime shift, sparse transfer.

Почему важно: следующий шаг должен быть основан не на static best rules, а на правилах, которые стабильны во времени и не зависят от одного события или режима.

## 23.4 Event-Aware Risk Overlay v1

Статус: реализовано как opt-in research/diagnostic overlay. Production consumer logic по умолчанию не меняется.

Цель: заменить hard event risk filter на мягкий overlay: risk score, position multiplier, probability addon, RR multiplier и warnings.

Что сделано:

- добавлен opt-in overlay для `/signals/consumer.json` и `/signals/consumer/{ticker}.json`;
- добавлен endpoint `/signals/consumer/event-risk-overlay-compare`;
- добавлен endpoint `/signals/event-aware/risk-overlay-backtest`;
- добавлена page `/signals/event-aware/risk-overlay-page`;
- режимы: `diagnostic_only`, `soft_adjust`, `experimental_downgrade`;
- action меняется только в explicit `experimental_downgrade` при high/extreme risk.

Почему важно: hard filter ухудшал walk-forward из-за missed winners; overlay снижает exposure и повышает требования, не превращая event layer в production short/avoid engine.

## 23.5 Event-Aware Risk Overlay Walk-forward Validation

Статус: реализовано как leakage-safe validation layer для soft overlay. Research result: PF/return/stop-hit exposure improved, но overlay был слишком агрессивным (`avg_position_multiplier` около `0.293`).

Цель: проверить, переносится ли улучшение static overlay backtest на future folds, когда параметры overlay выбираются только на прошлом train window.

Что сделано:

- добавлен endpoint `/signals/event-aware/risk-overlay-walk-forward`;
- добавлена page `/signals/event-aware/risk-overlay-walk-forward-page`;
- train folds выбирают bounded config grid по risk-adjusted score;
- если train не находит полезный overlay, fold выбирает `disabled`;
- test folds сравнивают baseline full exposure vs weighted overlay exposure;
- summary показывает return/PF/stop-hit exposure deltas, exposure reduction, positive folds и config frequency.

Почему важно: overlay может стать production default только после leakage-safe проверки, а не по static historical fit.

## 23.6 Conservative Event Risk Overlay Calibration

Статус: реализовано как research calibration layer. Result: `conservative_overlay_candidate`.

Цель: найти более мягкий overlay, который сохраняет PF/stop-hit improvements без чрезмерного снижения exposure.

Что сделано:

- добавлен endpoint `/signals/event-aware/risk-overlay-conservative-calibration`;
- добавлена page `/signals/event-aware/risk-overlay-conservative-page`;
- config grid использует более высокие thresholds и более мягкие multipliers;
- train folds выбирают только configs, проходящие constraints по `avg_position_multiplier` и `exposure_reduction`;
- test folds проверяют return/PF/stop-hit deltas на future samples;
- добавлен benchmark comparison: disabled, aggressive overlay, default soft overlay и selected conservative config.

Почему важно: soft overlay полезен только если улучшает риск без превращения портфеля в почти нулевую экспозицию.

## 23.7 Conservative Event Overlay Paper Integration

Статус: реализовано как opt-in paper-trading/report integration. Production defaults не меняются.

Цель: сделать выбранный conservative overlay удобным для текущих consumer signals и paper snapshot без action downgrade.

Что сделано:

- добавлен shortcut query flag `use_conservative_event_overlay=true`;
- shortcut использует config `cons_t20_40_60_80_m95_e80_h65_x40_w100`;
- разрешены только `soft_adjust` и `diagnostic_only`;
- consumer forecast/list показывают base size, adjusted size, multiplier, risk level, reasons и research basis;
- добавлен read-only endpoint `/signals/event-aware/conservative-overlay-paper-snapshot`;
- добавлена page `/signals/event-aware/conservative-overlay-paper-page`;
- signal audit получил отдельный layer `conservative_event_overlay`.

Почему важно: это переводит validated research result в удобный paper-tracking формат без включения production default.

## 23.8 Conservative Event Overlay Paper Tracking

Статус: реализовано как local paper-tracking layer. Production defaults не меняются.

Цель: сохранять conservative overlay snapshots и позже оценивать realized baseline vs overlay outcome по локальным свечам.

Что сделано:

- добавлены таблицы `event_overlay_paper_snapshots` и `event_overlay_paper_snapshot_items`;
- добавлен write endpoint `POST /signals/event-aware/conservative-overlay-paper-snapshots`;
- добавлены read endpoints для list/detail/dashboard;
- добавлен evaluate endpoint `POST /signals/event-aware/conservative-overlay-paper-snapshots/{snapshot_id}/evaluate`;
- добавлена page `/signals/event-aware/conservative-overlay-paper-tracking-page`;
- evaluation считает realized return, baseline PnL, overlay PnL, overlay delta и breakdown by risk level.

Почему важно: текущий snapshot показывает только сегодняшнюю структуру риска, а paper tracking позволяет измерить будущий realized эффект без реальных сделок и без включения overlay в production.

## 24. Production News Pipeline

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

## 19. Signal History / Paper Trading

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

## 20. Portfolio Risk Office

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

## 21. Production Layer

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
