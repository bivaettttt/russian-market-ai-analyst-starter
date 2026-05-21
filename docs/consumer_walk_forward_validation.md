# Consumer Walk-Forward Validation

Walk-forward validation проверяет, насколько threshold sweep устойчив во времени. Вместо выбора лучшего config на одном историческом срезе процесс делит samples по датам:

1. На train window выбирает лучший threshold config.
2. На следующем test window проверяет этот config.
3. Повторяет rolling/fold splits.
4. Сравнивает train score и test score.

Это защищает от переоптимизации параметров под один участок истории.

## Зачем после threshold sweep

Threshold sweep показывает лучшие configs на всём доступном proxy-наборе.

Walk-forward отвечает на другой вопрос: если config был выбран на прошлом периоде, сохраняет ли он качество на будущем периоде.

## Train Score vs Test Score

- `train_score`: score выбранного config на train window.
- `test_score`: score того же config на следующем test window.

Хорошая конфигурация не обязана иметь максимальный train score, но должна сохранять приемлемый test score.

## Score Decay

`score_decay = train_score - test_score`

Малый decay означает, что config лучше обобщается на следующий период. Большой decay говорит о вероятной переоптимизации.

## Generalization Ratio

`generalization_ratio = test_score / train_score`, если `train_score > 0`.

Интерпретация:

- около `1.0`: test похож на train;
- меньше `0.5`: сильная деградация;
- `null`: train score не положительный или недостаточно данных.

## Stability Label

- `stable`: test score положительный, score decay умеренный, test signals достаточно, stop hit не стал резко хуже.
- `moderate`: test score около нуля или выше, decay приемлемый.
- `unstable`: test результат резко хуже train.
- `insufficient_data`: мало train/test samples или мало test signals.

## Recommended Config

`recommended_config` выбирается как наиболее частый selected config среди folds. Он не применяется автоматически в production.

Перед изменением production thresholds нужно проверить:

- другой период истории;
- чувствительность к universe;
- sector concentration;
- комиссии, спреды и проскальзывание;
- поведение на кризисных режимах;
- соответствие risk policy.

## Ограничения

- Используется proxy historical audit, а не полный replay live endpoint.
- Нет комиссий, налогов, спредов и проскальзывания.
- Дневная свеча не даёт intraday order; если target и stop задеты в одной свече, считается `stop_hit`.
- Historical ticker news и global macro/geopolitical events не replay-ятся полноценно.
- Возможен survivorship bias из-за текущего instrument universe.
- Selected config не применяется автоматически к production decision logic.

## Curl Examples

Quick:

```bash
curl -s "http://127.0.0.1:8000/signals/consumer/walk-forward?max_tickers=10&max_samples=300&max_configs=40&folds=2"
```

Medium:

```bash
curl -s "http://127.0.0.1:8000/signals/consumer/walk-forward?max_tickers=50&max_samples=2000&max_configs=100&folds=3"
```

Custom grid:

```bash
curl -s "http://127.0.0.1:8000/signals/consumer/walk-forward?max_tickers=30&max_samples=1200&max_configs=80&folds=3&horizons=20,30&target_pcts=0.04,0.05&stop_pcts=0.03&min_probabilities=50,55,60&min_ml_probabilities=20,30&min_rr_values=1.0,1.2"
```

HTML page:

```bash
curl -s "http://127.0.0.1:8000/signals/consumer/walk-forward-page"
```
