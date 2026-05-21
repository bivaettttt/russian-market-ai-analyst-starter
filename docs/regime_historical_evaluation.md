# Regime-Aware Historical Evaluation

Regime-aware historical evaluation проверяет, помогает ли `market_regime` на истории, а не только выглядит полезно в live forecast.

## Зачем Это Нужно

Live `/signals/market-regime` показывает текущий режим рынка, но не доказывает, что фильтр снижает плохие long-входы. Historical evaluation считает режим рынка на каждую историческую дату и сравнивает outcomes до и после применения risk-off фильтра.

## Как Считается Historical Regime

Для каждой исторической точки берутся только свечи до даты D включительно. По текущему universe строятся breadth и downside metrics:

- доля тикеров выше SMA20;
- доля с положительной 5d и 20d доходностью;
- доля с `ret20 < -5%`;
- доля около 20d low;
- средняя 20d volatility;
- средняя 20d return.

Будущие свечи используются только для outcome: `target_hit`, `stop_hit`, `timeout`.

## By Market Regime

`by_market_regime` показывает bucket metrics по режимам:

- `risk_on`
- `neutral`
- `risk_off`
- `unknown`

Ключевые поля:

- `samples`
- `target_hit_rate_pct`
- `stop_hit_rate_pct`
- `timeout_rate_pct`
- `avg_forward_return_pct`
- `avg_mfe_pct`
- `avg_mae_pct`
- `avg_audit_score`
- `avg_regime_score`
- `long_allowed_rate_pct`

## Regime Filter Comparison

`regime_filter_comparison` сравнивает:

- `baseline`: все proxy historical samples;
- `with_regime_filter`: samples после исключения long-сигналов, где historical regime был `risk_off` и `long_allowed=false`;
- `delta`: разница по сигналам, hit-rate, stop-rate, return и coverage.

Если `stop_hit_rate_pct` снизился, фильтр потенциально помогает risk control. Если signals сильно упали, а return не улучшился, фильтр может быть слишком строгим или regime proxy недостаточно точным.

## Интерпретация

Если `risk_off_stop_hit_rate_pct` высокий:

- long-сигналы в risk-off действительно опасны;
- стоит проверять, сколько таких сигналов фильтр убирает;
- next step: sector/regime-specific thresholds.

Если filter уменьшил signals, но не улучшил return:

- фильтр режет coverage без качества;
- нужно проверить thresholds `long_allowed`, `downside_pressure`, `regime_score`;
- возможно, risk-off полезен только для отдельных секторов.

## Curl Examples

```bash
curl "http://127.0.0.1:8010/signals/consumer/regime-historical-evaluation?max_tickers=10&max_samples=300"
```

```bash
curl "http://127.0.0.1:8010/signals/consumer/backtest-audit?max_tickers=10&max_samples=200&use_market_regime_filter=true"
curl "http://127.0.0.1:8010/signals/consumer/threshold-sweep?max_tickers=10&max_samples=200&max_configs=40&use_market_regime_filter=true"
curl "http://127.0.0.1:8010/signals/consumer/walk-forward?max_tickers=10&max_samples=300&max_configs=40&folds=2&use_market_regime_filter=true"
```

## Limitations

- Это proxy historical evaluation, не полный replay live consumer endpoint.
- Нет комиссий, проскальзывания, налогов и спредов.
- Дневные свечи не дают порядок high/low внутри дня.
- Historical news/global context не replayed в этом слое.
- Universe строится по текущим инструментам, возможен survivorship bias.
- Historical regime approximate и не применяет параметры в production автоматически.
