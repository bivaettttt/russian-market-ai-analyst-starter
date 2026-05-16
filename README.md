# Russian Market AI Analyst — Starter

Локальный MVP финансового AI-аналитика для российского фондового рынка.

Цель первой версии: загрузить котировки с MOEX ISS, хранить их локально, принимать текст новости/события и возвращать первичную AI-классификацию влияния на российские активы.

## Что уже есть в стартере

- FastAPI backend.
- Клиент MOEX ISS для дневных свечей по акциям TQBR.
- Локальная база через SQLAlchemy: SQLite по умолчанию, PostgreSQL опционально.
- Каркас клиента Ollama.
- Rule-based fallback, если Ollama не запущена.
- API для загрузки свечей и анализа текстового события.
- Docker Compose для PostgreSQL, Qdrant, Redis и Ollama.

## Быстрый старт без Docker

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python ../scripts/init_db.py
uvicorn app.main:app --reload
```

Откройте:

```text
http://127.0.0.1:8000/docs
```

## Быстрый старт с Docker-инфраструктурой

```bash
docker compose up -d postgres qdrant redis ollama
```

Затем backend можно запускать локально или добавить отдельный контейнер позднее.

## Пример загрузки свечей

```bash
curl -X POST "http://127.0.0.1:8000/ingest/moex/SBER?from_date=2024-01-01&to_date=2024-12-31"
```

Получить свечи:

```bash
curl "http://127.0.0.1:8000/candles/SBER?limit=10"
```

## Пример анализа новости

```bash
curl -X POST "http://127.0.0.1:8000/analyze/news" \
  -H "Content-Type: application/json" \
  -d '{"text":"Совет директоров рекомендовал дивиденды выше ожиданий рынка. Компания сообщает о росте свободного денежного потока.","source":"manual"}'
```

## Источники данных для первого MVP

- MOEX ISS: котировки, свечи, справочник инструментов.
- ЦБ РФ: курсы валют, ключевая ставка, инфляция, RUONIA.
- e-disclosure: раскрытие эмитентов.
- Федресурс: юридически значимые сведения.
- Росстат и Минфин: макроэкономика, ОФЗ, бюджетные данные.

## Следующий этап

1. Добавить загрузчик списка бумаг TQBR.
2. Добавить дивидендный календарь.
3. Добавить парсер e-disclosure.
4. Добавить Qdrant для поиска по новостям и раскрытиям.
5. Добавить Neo4j для графа связей: эмитент → сектор → драйверы → активы.
6. Сделать daily briefing по рынку РФ.

## Дисклеймер

Это исследовательский и аналитический инструмент. Он не является индивидуальной инвестиционной рекомендацией.


## Portfolio Constructor & Snapshots

В проект добавлен модуль конструктора портфеля на основе текущих технических сигналов.

### Основные возможности

- сбор модельного портфеля по бюджету, риск-профилю, горизонту и режиму качества;
- учёт lot_size инструментов MOEX;
- расчёт целевого потенциала, стоп-риска и risk/reward;
- экспорт портфеля в CSV;
- сохранение portfolio snapshots;
- история snapshot-ов;
- детальная HTML-страница snapshot-а;
- сравнение двух snapshot-ов;
- CSV-экспорт сравнения;
- удаление snapshot-ов;
- статистика по сохранённым snapshot-ам;
- карточка последнего и лучшего portfolio snapshot на dashboard.

### Portfolio endpoints

```text
GET    /portfolio/construct/demo
POST   /portfolio/construct
POST   /portfolio/construct.csv

POST   /portfolio/construct/snapshot
GET    /portfolio/construct/snapshots
GET    /portfolio/construct/snapshots.csv
GET    /portfolio/construct/snapshots/latest
GET    /portfolio/construct/snapshots/stats
GET    /portfolio/construct/snapshots/{snapshot_id}
GET    /portfolio/construct/snapshots/{snapshot_id}/view
DELETE /portfolio/construct/snapshots/{snapshot_id}

GET    /portfolio/construct/history
GET    /portfolio/construct/compare
GET    /portfolio/construct/compare.json
GET    /portfolio/construct/compare.csv
```

### Пример сборки портфеля

```bash
curl -X POST "http://127.0.0.1:8000/portfolio/construct" \
  -H "Content-Type: application/json" \
  -d '{"budget":100000,"risk_profile":"balanced","horizon":"medium","quality_mode":"normal"}'
```

### Пример сохранения snapshot-а

```bash
curl -X POST "http://127.0.0.1:8000/portfolio/construct/snapshot" \
  -H "Content-Type: application/json" \
  -d '{"budget":100000,"risk_profile":"balanced","horizon":"medium","quality_mode":"normal"}'
```

### Пример сравнения snapshot-ов

```bash
curl "http://127.0.0.1:8000/portfolio/construct/compare.json?left_id=1&right_id=2"
```


## Smoke test

После запуска backend можно проверить основные страницы и API одной командой:

```bash
./scripts/smoke_test.sh
```

По умолчанию скрипт проверяет `http://127.0.0.1:8000` и удаляет test snapshot-ы, которые сам создал.

Для другого адреса:

```bash
BASE_URL="http://127.0.0.1:8001" ./scripts/smoke_test.sh
```

Если нужно оставить test snapshot-ы для ручной проверки:

```bash
CLEANUP_SMOKE_SNAPSHOTS=0 ./scripts/smoke_test.sh
```

## Clean archive

Чтобы собрать архив проекта без `.venv`, SQLite-базы, `__pycache__`, `.DS_Store` и других runtime-файлов:

```bash
./scripts/make_clean_archive.sh
```

Можно указать имя файла:

```bash
./scripts/make_clean_archive.sh russian-market-ai-analyst-starter-clean.zip
```
