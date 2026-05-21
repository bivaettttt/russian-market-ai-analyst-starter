# Stabilization Notes

Этот этап стабилизирует Research Alpha+ проект без изменения бизнес-логики consumer signal model.

## Что Сделано

- Добавлен `pytest.ini`, чтобы `python3 -m pytest -q` работал из корня проекта без `PYTHONPATH=backend`.
- Исправлен `SyntaxWarning` в `backend/app/services/ticker_page_html.py`: JS regex внутри Python HTML string теперь экранирован корректно.
- Расширен `scripts/smoke_test.sh` новыми consumer validation endpoints:
  - `/signals/market-regime`
  - `/signals/consumer/backtest-audit`
  - `/signals/consumer/backtest-audit-page`
  - `/signals/consumer/threshold-sweep`
  - `/signals/consumer/threshold-sweep-page`
  - `/signals/consumer/walk-forward`
  - `/signals/consumer/walk-forward-page`
  - consumer list сценарии `long`, `downside`, `all&news=with_events`
- Добавлены быстрые contract tests:
  - `tests/test_market_regime.py`
  - `tests/test_signal_audit_contract.py`
  - `tests/test_backtest_audit_contract.py`
- Обновлён `README.md` под текущий статус Research Alpha+ / Validation Engine.
- Добавлен `docs/ROADMAP.md`.

## Что Намеренно Не Трогали

- Consumer decision logic.
- Actions/recommendations и публичный смысл API-полей.
- Production thresholds.
- ML training и признаки модели.
- News/global macro бизнес-правила.
- Deployment/auth/monitoring слой.

## Почему Это Важно

Перед следующим этапом `regime-aware historical evaluation` проекту нужен воспроизводимый базовый контур: тесты, compile checks, smoke-test новых endpoints и актуальная документация. Это снижает риск случайно сломать текущую модель во время будущей калибровки.
