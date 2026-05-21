# Russian Market AI Analyst

Research Alpha+ / Validation Engine для сигналов по инструментам МосБиржи.

Проект вырос из starter/MVP в локальный исследовательский движок, который строит объяснимые consumer-сигналы, проверяет их на истории и показывает диагностику качества принятия решения. Это аналитический инструмент, не индивидуальная инвестиционная рекомендация.

## Что Умеет

- Consumer signals API и UI: `/signals`.
- Сценарии сигналов: `long`, `downside`, `all`.
- Technical layer: тренд, momentum, волатильность, target/stop proxy.
- ML probability layer: вероятность достижения цели и ML-корректировка.
- Risk layer: risk/reward, stop distance, target distance, veto-фильтры.
- Position sizing: ограничение размера позиции по качеству сигнала и риску.
- Ticker news layer: локальные события по тикеру.
- Global macro/geopolitical layer: ставки, санкции, FX, нефть, risk-off, geopolitical shocks.
- Market regime filter: `risk_on`, `neutral`, `risk_off` по ширине рынка, downside pressure и волатильности.
- Signal audit: layer-by-layer explanation от technical/ML/risk/news/macro/regime до final verdict.
- Backtest audit: proxy historical evaluation consumer-модели.
- Threshold sweep: перебор порогов probability/ML/RR/target/stop/horizon.
- Walk-forward validation: train/test проверка устойчивости threshold config.
- Portfolio constructor, snapshots, compare, CSV exports.
- AI reports, report history and trends.

## Запуск

```bash
cd /Users/bivaettttt/Desktop/russian-market-ai-analyst-starter
source backend/.venv/bin/activate
cd backend
uvicorn app.main:app --reload --host 127.0.0.1 --port 8010
```

Если виртуальное окружение ещё не создано:

```bash
cd /Users/bivaettttt/Desktop/russian-market-ai-analyst-starter/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python ../scripts/init_db.py
uvicorn app.main:app --reload --host 127.0.0.1 --port 8010
```

## Главные Страницы

- `/signals` — consumer signals UI.
- `/signals/consumer/backtest-audit-page` — historical backtest audit.
- `/signals/consumer/threshold-sweep-page` — threshold sweep / grid search.
- `/signals/consumer/walk-forward-page` — walk-forward validation.
- `/signals/market-regime` — live market regime JSON.
- `/ticker/SBER` — карточка тикера.
- `/portfolio/construct/demo` — portfolio constructor.
- `/ai/report/demo` — AI report demo.

## Быстрые Проверки

Из корня проекта:

```bash
python3 -m pytest -q
python3 -m compileall -q backend/app
BASE_URL=http://127.0.0.1:8010 ./scripts/smoke_test.sh
```

`pytest.ini` добавляет `backend` в `pythonpath`, поэтому `PYTHONPATH=backend` больше не нужен.

## Важные Endpoints

Consumer signals:

```text
GET /signals/consumer.json
GET /signals/consumer/{ticker}.json
GET /signals/market-regime
```

Validation:

```text
GET /signals/consumer/backtest-audit
GET /signals/consumer/threshold-sweep
GET /signals/consumer/walk-forward
```

News/events:

```text
POST /analyze/news
GET  /events
```

Universe and ticker pages:

```text
GET  /tickers/search
GET  /tickers/universe
POST /system/update-universe
POST /system/update-candles/all
GET  /ticker/{ticker}
GET  /tickers/{ticker}
```

Portfolio:

```text
GET    /portfolio/construct/demo
POST   /portfolio/construct
POST   /portfolio/construct.csv
POST   /portfolio/construct/snapshot
GET    /portfolio/construct/snapshots
GET    /portfolio/construct/compare
GET    /portfolio/construct/compare.json
GET    /portfolio/construct/compare.csv
```

## Примеры Curl

```bash
curl "http://127.0.0.1:8010/signals/consumer.json?limit=20&scenario=long"
curl "http://127.0.0.1:8010/signals/consumer/SBER.json"
curl "http://127.0.0.1:8010/signals/market-regime"
```

```bash
curl "http://127.0.0.1:8010/signals/consumer/backtest-audit?max_tickers=10&max_samples=200"
curl "http://127.0.0.1:8010/signals/consumer/threshold-sweep?max_tickers=10&max_samples=200&max_configs=40"
curl "http://127.0.0.1:8010/signals/consumer/walk-forward?max_tickers=10&max_samples=300&max_configs=40&folds=2"
```

```bash
curl -X POST "http://127.0.0.1:8010/analyze/news" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "ЦБ снизил ключевую ставку",
    "text": "Снижение ключевой ставки поддерживает ОФЗ, банки и rate-sensitive сектора.",
    "source": "manual_test"
  }'
```

## Текущий Статус

Статус проекта: Research Alpha+ / Validation Engine.

Последняя walk-forward диагностика показала, что текущие threshold-конфигурации требуют калибровки: test score слабый, stop-hit rate высокий, устойчивость ограничена. Поэтому текущий фокус — validation, market regime filtering, calibration и paper-trading контур, а не обещание готовой production-модели.

## Ограничения

- Backtest audit является proxy historical audit, а не полным replay live endpoint.
- Нет учёта комиссий, налогов, спредов и проскальзывания.
- Дневные свечи не дают порядок `high/low` внутри дня; same-day target/stop считается консервативно.
- Historical news/global context приближённый и не всегда replayed.
- Возможен survivorship bias из-за текущего instrument universe.
- Пороговые параметры не применяются в production автоматически после sweep/walk-forward.
- Проект не должен использоваться как автоматический trading bot без независимой валидации, мониторинга и юридической проверки.

## Документация

- `docs/signal_audit_layer.md`
- `docs/consumer_signal_backtest_audit.md`
- `docs/consumer_threshold_sweep_audit.md`
- `docs/consumer_walk_forward_validation.md`
- `docs/market_regime_filter.md`
- `docs/ROADMAP.md`
- `docs/STABILIZATION_NOTES.md`

## Архив

Собрать чистый архив без `.venv`, SQLite-базы, `__pycache__`, `.DS_Store` и runtime-файлов:

```bash
./scripts/make_clean_archive.sh
```
