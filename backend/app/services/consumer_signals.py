from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import or_, select, func
from sqlalchemy.orm import Session

from app.models import MarketEvent
from app.services.ticker_data import get_ticker_snapshot
from app.models import Candle, Instrument
from app.services.consumer_probability import build_probability_assessment
from app.services.ml_probability_engine import predict_ml_probability_for_ticker

CONSUMER_SIGNAL_MODEL_VERSION = "tech_v4_quality_rr"

ACTION_RANK = {
    "buy": 1,
    "consider_buy": 2,
    "watch_ml_confirmed": 3,
    "watch_ml_rejected": 4,
    "watch": 5,
    "watch_bad_rr": 6,
    "avoid_bad_target": 7,
    "avoid_bad_rr": 8,
    "avoid_ml_veto": 9,
    "avoid_ml_filter": 9,
    "avoid_risk": 10,
    "avoid": 11,
    "no_forecast": 9,
    "no_data": 9,
    "no_price": 9,

    # legacy actions
    "buy_watch": 2,
    "watch_buy": 2,
    "hold_watch": 4,
    "risk_sell_watch": 6,
}


def _to_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _round(value: Any, digits: int = 2) -> float | None:
    number = _to_float(value)
    if number is None:
        return None
    return round(number, digits)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _pct_change(current: float | None, previous: float | None) -> float | None:
    if current is None or previous in (None, 0):
        return None
    return (current - previous) / previous * 100


def _event_to_dict(event: MarketEvent) -> dict[str, Any]:
    created_at = getattr(event, "created_at", None)
    if isinstance(created_at, datetime):
        created_value = created_at.isoformat()
    else:
        created_value = str(created_at) if created_at else None

    return {
        "id": getattr(event, "id", None),
        "title": getattr(event, "title", None) or "Событие рынка",
        "source": getattr(event, "source", None),
        "url": getattr(event, "url", None),
        "importance": getattr(event, "importance", None),
        "impact": getattr(event, "impact", None),
        "created_at": created_value,
        "reasoning": getattr(event, "reasoning", None),
    }


def list_related_events(
    db: Session,
    ticker: str,
    limit: int = 3,
) -> list[dict[str, Any]]:
    ticker = ticker.upper().strip()

    rows = db.scalars(
        select(MarketEvent)
        .where(
            or_(
                MarketEvent.affected_assets.ilike(f"%{ticker}%"),
                MarketEvent.title.ilike(f"%{ticker}%"),
                MarketEvent.text.ilike(f"%{ticker}%"),
            )
        )
        .order_by(MarketEvent.created_at.desc())
        .limit(limit)
    ).all()

    return [_event_to_dict(row) for row in rows]


def _build_unified_signal(
    candles: list[dict[str, Any]],
    latest: dict[str, Any],
    technical: dict[str, Any],
    fallback_signal: dict[str, Any],
) -> dict[str, Any]:
    try:
        from app.services.signals_backtest import build_historical_signal_v4

        candle = candles[-1] if candles else latest
        signal = build_historical_signal_v4(
            history=candles or [latest],
            candle=candle,
            technical=technical,
        )
        signal["model_version"] = CONSUMER_SIGNAL_MODEL_VERSION
        return signal
    except Exception as exc:
        signal = dict(fallback_signal or {})
        signal["model_version"] = "fallback_consumer_signal"
        signal["fallback_error"] = str(exc)
        return signal


def _recommendation_from_action(action: str | None, probability: float | None) -> tuple[str, str]:
    probability = probability or 0

    if action in {"buy_watch", "watch_buy"}:
        if probability >= 70:
            return "Покупать", "positive"
        return "Можно рассмотреть", "positive"

    if action == "risk_sell_watch":
        return "Высокий риск", "negative"

    return "Наблюдать", "neutral"


def _derive_target_price(
    price: float | None,
    signal: dict[str, Any],
    technical: dict[str, Any],
) -> float | None:
    explicit_target = _to_float(signal.get("target_price"))

    if price is None:
        return round(explicit_target, 2) if explicit_target is not None else None

    action = signal.get("action")
    recent_high = _to_float(technical.get("recent_high"))
    recent_low = _to_float(technical.get("recent_low"))
    sma_20 = _to_float(technical.get("sma_20"))
    sma_50 = _to_float(technical.get("sma_50"))
    volatility = _to_float(technical.get("volatility_20d_pct")) or 1.5

    normalized_volatility = min(max(volatility, 1.0), 4.0)

    if action == "risk_sell_watch":
        if explicit_target is not None and explicit_target < price:
            return round(explicit_target, 2)

        candidate = min(
            price * (1 - normalized_volatility / 100 * 2),
            recent_low or price,
        )
        return round(candidate, 2)

    # Consumer long targets must not be almost equal to current price.
    # If an upstream model gives a tiny target like +0.2%, normalize it
    # using volatility and nearby technical levels.
    min_upside_pct = max(2.8, min(5.5, normalized_volatility * 1.8))
    minimum_consumer_target = price * (1 + min_upside_pct / 100)

    candidates = [minimum_consumer_target]

    if explicit_target is not None and explicit_target > price * 1.02:
        candidates.append(explicit_target)

    if recent_high is not None and recent_high > price * 1.01:
        candidates.append(recent_high)

    if sma_20 is not None and sma_20 > price * 1.01:
        candidates.append(sma_20)

    if sma_50 is not None and sma_50 > price * 1.01:
        candidates.append(sma_50)

    if action in {"buy_watch", "watch_buy"}:
        candidates.append(price * 1.035)

    candidate = max(candidates)

    # Do not create unrealistic consumer targets from a single noisy level.
    max_reasonable_target = price * (1 + max(8.0, normalized_volatility * 3.2) / 100)

    return round(min(candidate, max_reasonable_target), 2)


def _derive_forecast_range(
    price: float | None,
    target: float | None,
    signal: dict[str, Any],
    technical: dict[str, Any],
) -> dict[str, float | None]:
    if price is None:
        return {"low": None, "high": None}

    action = signal.get("action")
    recent_high = _to_float(technical.get("recent_high"))
    recent_low = _to_float(technical.get("recent_low"))
    volatility = _to_float(technical.get("volatility_20d_pct")) or 1.5
    vol_buffer = min(max(volatility, 0.8), 4.5) / 100

    if action == "risk_sell_watch":
        low = min(recent_low or price * (1 - vol_buffer * 3), target or price)
        high = price * (1 + vol_buffer * 1.2)
        return {"low": round(low, 2), "high": round(high, 2)}

    if action in {"buy_watch", "watch_buy"}:
        low = max(0, price * (1 - vol_buffer * 1.6))
        high = max(target or price, recent_high or price, price * (1 + vol_buffer * 2.2))
        return {"low": round(low, 2), "high": round(high, 2)}

    low = min(recent_low or price * (1 - vol_buffer * 1.6), price * (1 - vol_buffer * 1.2))
    high = max(target or price, recent_high or price, price * (1 + vol_buffer * 1.6))
    return {"low": round(low, 2), "high": round(high, 2)}


def _calculate_target_probability(
    signal: dict[str, Any],
    technical: dict[str, Any],
    price: float | None,
    target_price: float | None,
    events: list[dict[str, Any]],
) -> float | None:
    if price is None or target_price is None:
        return None

    action = signal.get("action")
    confidence = _to_float(signal.get("confidence_pct"))
    quality = _to_float(signal.get("quality_score"))
    rr = _to_float(signal.get("risk_reward_ratio"))
    return_5d = _to_float(technical.get("return_5d_pct"))
    return_20d = _to_float(technical.get("return_20d_pct"))
    volume_ratio = _to_float(technical.get("volume_ratio"))
    volatility = _to_float(technical.get("volatility_20d_pct"))

    probability = confidence if confidence is not None else 50.0

    if quality is not None:
        probability += (quality - 50.0) * 0.28

    if rr is not None:
        if rr >= 1.8:
            probability += 8
        elif rr >= 1.2:
            probability += 4
        elif rr < 0.8:
            probability -= 10
        else:
            probability -= 4

    upside_pct = _pct_change(target_price, price)
    if upside_pct is not None:
        if action == "risk_sell_watch":
            # Для risk-сигнала цель часто ниже текущей цены. Тогда вероятность достижения цели снижения растёт.
            downside_pct = abs(upside_pct)
            if downside_pct <= 2:
                probability += 6
            elif downside_pct >= 8:
                probability -= 8
        else:
            if upside_pct <= 2:
                probability += 5
            elif upside_pct <= 5:
                probability += 1
            elif upside_pct >= 12:
                probability -= 10
            elif upside_pct >= 8:
                probability -= 5

    if return_5d is not None:
        if return_5d > 1:
            probability += 3 if action != "risk_sell_watch" else -2
        elif return_5d < -1:
            probability -= 3 if action != "risk_sell_watch" else -1

    if return_20d is not None:
        if return_20d > 3:
            probability += 2 if action != "risk_sell_watch" else -2
        elif return_20d < -4:
            probability -= 4 if action != "risk_sell_watch" else 2

    if volume_ratio is not None:
        if volume_ratio >= 1.3:
            probability += 3
        elif volume_ratio < 0.6:
            probability -= 4

    if volatility is not None:
        if volatility >= 3.0:
            probability -= 8
        elif volatility <= 1.2:
            probability += 2

    for event in events:
        impact = str(event.get("impact") or "").lower()
        importance = _to_float(event.get("importance")) or 0
        weight = min(max(importance, 1), 5)

        if "positive" in impact or "позит" in impact:
            probability += weight
        elif "negative" in impact or "негат" in impact:
            probability -= weight

    if action == "risk_sell_watch":
        probability = _clamp(probability, 12, 88)
    else:
        probability = _clamp(probability, 8, 92)

    return round(probability, 0)


def _build_explanation(
    signal: dict[str, Any],
    technical: dict[str, Any],
    events: list[dict[str, Any]],
    probability: float | None,
    probability_assessment: dict[str, Any] | None = None,
    ml_probability_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    technical_factors = []

    if technical.get("trend"):
        technical_factors.append(f"Тренд: {technical.get('trend')}.")
    if technical.get("return_5d_pct") is not None:
        technical_factors.append(f"Динамика за 5 свечей: {technical.get('return_5d_pct')}%.")
    if technical.get("return_20d_pct") is not None:
        technical_factors.append(f"Динамика за 20 свечей: {technical.get('return_20d_pct')}%.")
    if technical.get("volume_ratio") is not None:
        technical_factors.append(f"Объём к среднему: {technical.get('volume_ratio')}x.")

    for reason in signal.get("reasons") or []:
        if reason and len(technical_factors) < 7:
            technical_factors.append(str(reason))

    news_factors = []
    if events:
        for event in events[:3]:
            title = event.get("title") or "Событие рынка"
            impact = event.get("impact") or "влияние не определено"
            news_factors.append(f"{title} — {impact}.")
    else:
        news_factors.append("Свежих событий по тикеру в базе не найдено; прогноз основан главным образом на цене и объёмах.")

    risk_factors = []
    risk_level = signal.get("risk_level")
    if risk_level:
        risk_factors.append(f"Риск сценария: {risk_level}.")
    if signal.get("stop_loss") is not None:
        risk_factors.append(f"Сценарий лучше пересмотреть около {signal.get('stop_loss')}.")
    if signal.get("risk_reward_ratio") is not None:
        risk_factors.append(f"Соотношение потенциальной цели и риска: {signal.get('risk_reward_ratio')}.")

    assessment = probability_assessment or {}
    reliability_level = assessment.get("reliability_level")
    reliability_reasons = assessment.get("reliability_reasons") or []
    calibration = assessment.get("calibration") or {}
    liquidity = assessment.get("liquidity") or {}

    ml_probability = _to_float((ml_probability_result or {}).get("ml_probability_pct")) if ml_probability_result else None

    if ml_probability_result and ml_probability_result.get("ok") and ml_probability is not None:
        technical_factors.append(
            f"ML-модель оценила вероятность достижения цели в {int(round(ml_probability))}%."
        )

        internal = assessment.get("internal") or {}
        ml_adjustment = internal.get("ml_adjustment_pct")
        ml_weight = internal.get("ml_weight")

        if ml_adjustment is not None and ml_weight is not None:
            direction = "повысила" if ml_adjustment > 0 else "снизила" if ml_adjustment < 0 else "не изменила"
            technical_factors.append(
                f"ML-корректировка {direction} итоговую вероятность на {abs(float(ml_adjustment)):.1f} п.п.; вес ML: {int(float(ml_weight) * 100)}%."
            )
    elif ml_probability_result and ml_probability_result.get("reason") == "model_not_trained":
        risk_factors.append("ML-модель ещё не обучена, используется базовая вероятностная оценка.")

    if reliability_level:
        risk_factors.append(f"Надёжность прогноза: {reliability_level}.")
    for reason in reliability_reasons[:3]:
        risk_factors.append(str(reason).capitalize() + ".")
    if calibration.get("samples"):
        risk_factors.append(
            f"Историческая проверка похожей цели: {calibration.get('success')} из {calibration.get('samples')} сценариев дошли до цели раньше стопа."
        )
    if liquidity.get("liquidity_bucket") == "low":
        risk_factors.append("Ликвидность ниже комфортной — возможны проскальзывание и резкие движения.")

    return {
        "summary": (
            f"Вероятность {int(probability) if probability is not None else '—'}% рассчитана по технической картине, "
            "исторической проверке достижения цели раньше стопа, ликвидности, объёму, риску сценария и доступным событиям."
        ),
        "technical": technical_factors or ["Технических факторов недостаточно."],
        "news": news_factors,
        "risks": risk_factors or ["Явные риск-факторы не выделены, но прогноз не является гарантией результата."],
    }



def _average(values: list[float]) -> float | None:
    clean = [float(value) for value in values if value is not None]

    if not clean:
        return None

    return sum(clean) / len(clean)


def _stddev(values: list[float]) -> float | None:
    clean = [float(value) for value in values if value is not None]

    if len(clean) < 2:
        return None

    avg = sum(clean) / len(clean)
    variance = sum((value - avg) ** 2 for value in clean) / (len(clean) - 1)

    return variance ** 0.5


def _build_consumer_regime_features(candles: list[dict[str, Any]]) -> dict[str, float | None]:
    """Lightweight regime features for adaptive ML weighting.

    These features intentionally mirror the regime evaluation layer, but are
    computed locally from the latest candle history so consumer scoring does
    not need to rebuild the ML dataset.
    """

    if not candles or len(candles) < 25:
        return {}

    closes = [_to_float(row.get("close")) for row in candles]
    highs = [_to_float(row.get("high")) for row in candles]
    lows = [_to_float(row.get("low")) for row in candles]
    volumes = [_to_float(row.get("volume")) for row in candles]
    values = [_to_float(row.get("value")) for row in candles]

    closes = [value for value in closes if value is not None]

    if len(closes) < 25:
        return {}

    current = closes[-1]

    if current is None or current <= 0:
        return {}

    recent_20 = closes[-20:]
    prev_20 = closes[-40:-20] if len(closes) >= 40 else []

    returns_20: list[float] = []

    for previous, current_close in zip(recent_20[:-1], recent_20[1:]):
        if previous and previous > 0:
            returns_20.append((current_close / previous - 1.0) * 100)

    volatility_20_pct = _stddev(returns_20)

    true_ranges: list[float] = []
    clean_highs = [value for value in highs if value is not None]
    clean_lows = [value for value in lows if value is not None]

    for index in range(max(1, len(candles) - 20), len(candles)):
        high = _to_float(candles[index].get("high"))
        low = _to_float(candles[index].get("low"))
        prev_close = _to_float(candles[index - 1].get("close"))

        if high is None or low is None or prev_close is None:
            continue

        true_ranges.append(
            max(
                high - low,
                abs(high - prev_close),
                abs(low - prev_close),
            )
        )

    atr_20 = _average(true_ranges)
    atr_20_pct = (atr_20 / current * 100) if atr_20 is not None and current else None

    recent_high_60 = max(clean_highs[-60:]) if len(clean_highs) >= 5 else None
    recent_low_60 = min(clean_lows[-60:]) if len(clean_lows) >= 5 else None

    if recent_high_60 is not None and recent_low_60 is not None and recent_high_60 > recent_low_60:
        range_position_60_pct = (current - recent_low_60) / (recent_high_60 - recent_low_60) * 100
    else:
        range_position_60_pct = None

    dist_low_60_pct = (
        (current - recent_low_60) / current * 100
        if recent_low_60 is not None and current
        else None
    )

    dist_high_60_pct = (
        (recent_high_60 - current) / current * 100
        if recent_high_60 is not None and current
        else None
    )

    ma_50 = _average(closes[-50:]) if len(closes) >= 50 else None
    ma_50_gap_pct = (
        (current / ma_50 - 1.0) * 100
        if ma_50 is not None and ma_50 > 0
        else None
    )

    ret_20 = (
        (current / closes[-21] - 1.0) * 100
        if len(closes) >= 21 and closes[-21] > 0
        else None
    )

    recent_values = [_to_float(row.get("value")) for row in candles[-20:]]
    previous_values = [_to_float(row.get("value")) for row in candles[-40:-20]]

    recent_value_avg = _average([value for value in recent_values if value is not None])
    previous_value_avg = _average([value for value in previous_values if value is not None])

    value_ratio_20 = (
        recent_value_avg / previous_value_avg
        if recent_value_avg is not None
        and previous_value_avg is not None
        and previous_value_avg > 0
        else None
    )

    return {
        "volatility_20_pct": volatility_20_pct,
        "atr_20_pct": atr_20_pct,
        "range_position_60_pct": range_position_60_pct,
        "dist_low_60_pct": dist_low_60_pct,
        "dist_high_60_pct": dist_high_60_pct,
        "ma_50_gap_pct": ma_50_gap_pct,
        "ret_20": ret_20,
        "value_ratio_20": value_ratio_20,
    }


def _regime_ml_multiplier(regime: dict[str, float | None]) -> tuple[float, str]:
    """Return ML weight multiplier and human-readable regime reason."""

    range_position = regime.get("range_position_60_pct")
    ma_50_gap = regime.get("ma_50_gap_pct")
    ret_20 = regime.get("ret_20")
    value_ratio = regime.get("value_ratio_20")
    dist_low = regime.get("dist_low_60_pct")
    volatility = regime.get("volatility_20_pct")
    atr = regime.get("atr_20_pct")

    strong_reasons: list[str] = []

    if range_position is not None and range_position >= 50:
        strong_reasons.append("цена находится в верхней части 60-дневного диапазона")

    if ma_50_gap is not None and ma_50_gap > 0:
        strong_reasons.append("цена выше MA50")

    if ret_20 is not None and ret_20 > 0:
        strong_reasons.append("20-дневный momentum положительный")

    if value_ratio is not None and value_ratio >= 1.02:
        strong_reasons.append("оборот выше среднего за предыдущий период")

    if dist_low is not None and 2.8 <= dist_low <= 7.7:
        strong_reasons.append("цена не у экстремального минимума, но близко к зоне восстановления")

    cautious_reasons: list[str] = []

    if volatility is not None and volatility <= 0.9:
        cautious_reasons.append("низкая 20-дневная волатильность")

    if atr is not None and atr <= 1.7:
        cautious_reasons.append("низкий ATR")

    if len(strong_reasons) >= 2:
        return 1.18, "regime boost: " + "; ".join(strong_reasons[:3])

    if len(strong_reasons) == 1:
        return 1.08, "regime mild boost: " + strong_reasons[0]

    if cautious_reasons:
        return 0.95, "regime cautious: " + "; ".join(cautious_reasons[:2])

    return 0.90, "regime neutral/unknown: ML не усиливается без подтверждающего режима"

def _adaptive_ml_weight(ml_probability: float | None, regime: dict[str, float | None] | None = None) -> float:
    """
    Evaluation-aware ML weight.

    Текущий threshold-report показал:
    - ML >= 30% даёт небольшой lift к base rate;
    - ML >= 40% исторически работает хуже base rate;
    - вероятности сжаты и не должны трактоваться как агрессивная уверенность.

    Поэтому ML сейчас используется в основном как risk-filter:
    низкий ML сильнее штрафует итоговую вероятность,
    высокий ML почти не бустит сигнал.
    """
    if ml_probability is None:
        return 0.0

    if ml_probability < 25:
        return 0.30

    if ml_probability < 30:
        return 0.24

    if ml_probability < 35:
        return 0.08

    if ml_probability < 40:
        return 0.14

    if ml_probability < 45:
        base_weight = 0.10
    else:
        base_weight = 0.02

    multiplier, _reason = _regime_ml_multiplier(regime or {})
    return round(max(0.02, min(0.18, base_weight * multiplier)), 4)


def _blend_rule_and_ml_probability(
    rule_probability: float | None,
    ml_probability: float | None,
    regime: dict[str, float | None] | None = None,
) -> dict[str, Any]:
    if rule_probability is None and ml_probability is None:
        return {
            "probability": None,
            "source": "none",
            "ml_weight": 0.0,
            "ml_adjustment_pct": None,
        }

    if rule_probability is None:
        return {
            "probability": round(float(ml_probability), 1) if ml_probability is not None else None,
            "source": "ml_only",
            "ml_weight": 1.0,
            "ml_adjustment_pct": None,
        }

    if ml_probability is None:
        return {
            "probability": round(float(rule_probability), 1),
            "source": "rule_only",
            "ml_weight": 0.0,
            "ml_adjustment_pct": 0.0,
        }

    ml_weight = _adaptive_ml_weight(ml_probability, regime=regime)
    rule_weight = 1.0 - ml_weight

    probability = round(rule_probability * rule_weight + ml_probability * ml_weight, 1)

    return {
        "probability": probability,
        "source": "rule_ml_adaptive_blend",
        "ml_weight": round(ml_weight, 2),
        "ml_adjustment_pct": round(probability - rule_probability, 1),
    }


def _consumer_signal_decision_gate(
    probability: float | None,
    reliability_level: str | None,
    risk_level: str | None,
    ml_adjustment_pct: float | None,
    ml_probability_pct: float | None,
    risk_reward_ratio: float | None = None,
    target_distance_pct: float | None = None,
) -> dict[str, Any]:
    probability_value = _to_float(probability)
    ml_adjustment = _to_float(ml_adjustment_pct)
    ml_probability = _to_float(ml_probability_pct)

    reliability = (reliability_level or "").lower()
    risk = (risk_level or "").lower()

    is_high_reliability = "выс" in reliability or "high" in reliability
    is_medium_reliability = "сред" in reliability or "medium" in reliability
    is_high_risk = "high" in risk or "выс" in risk or "risk" in risk or "риск" in risk

    if probability_value is None:
        return {
            "action": "no_forecast",
            "recommendation": "Недостаточно данных",
            "decision": "Прогноз пока не строится",
            "decision_level": "unknown",
            "decision_reason": "Недостаточно данных для расчёта вероятности.",
            "is_buy_candidate": False,
        }

    if is_high_risk and probability_value < 55:
        return {
            "action": "avoid_risk",
            "recommendation": "Не покупать",
            "decision": "Риск превышает ожидаемую доходность",
            "decision_level": "negative",
            "decision_reason": "Сигнал отфильтрован риск-блоком: вероятность недостаточна для текущего уровня риска.",
            "is_buy_candidate": False,
        }

    rr_value = _to_float(risk_reward_ratio)
    target_distance = _to_float(target_distance_pct)

    if target_distance is not None and target_distance <= 0 and probability_value >= 45:
        return {
            "action": "avoid_bad_target",
            "recommendation": "Не покупать",
            "decision": "Некорректная цель для long-сигнала",
            "decision_level": "negative",
            "decision_reason": "Целевая цена не выше текущей цены, поэтому покупка запрещена риск-блоком.",
            "is_buy_candidate": False,
        }

    if rr_value is not None and rr_value < 0.8 and probability_value >= 55:
        return {
            "action": "avoid_bad_rr",
            "recommendation": "Не покупать",
            "decision": "Слабое соотношение цель/риск",
            "decision_level": "negative",
            "decision_reason": "Потенциальная цель слишком мала относительно стопа: risk/reward ниже 0.8. Покупка запрещена риск-блоком.",
            "is_buy_candidate": False,
        }

    if rr_value is not None and 0.8 <= rr_value < 1.2 and probability_value >= 55:
        return {
            "action": "watch_bad_rr",
            "recommendation": "Наблюдать",
            "decision": "Недостаточное соотношение цель/риск",
            "decision_level": "neutral",
            "decision_reason": "Вероятность выглядит приемлемо, но risk/reward ниже 1.2. Покупка не разрешена, инструмент только в наблюдении.",
            "is_buy_candidate": False,
        }

    if ml_probability is not None and ml_probability < 15:
        return {
            "action": "avoid_ml_veto",
            "recommendation": "Не покупать",
            "decision": "ML-veto: модель против сценария",
            "decision_level": "negative",
            "decision_reason": "ML-модель оценивает вероятность достижения цели ниже 15%, поэтому сигнал не может быть покупкой даже при высокой rule-оценке.",
            "is_buy_candidate": False,
        }

    if ml_probability is not None and 15 <= ml_probability < 25 and probability_value >= 45:
        return {
            "action": "watch_ml_rejected",
            "recommendation": "Наблюдать",
            "decision": "Rule-сигнал есть, но ML не подтверждает покупку",
            "decision_level": "neutral",
            "decision_reason": "ML-модель оценивает вероятность достижения цели в зоне 15–25%, поэтому покупка запрещена; инструмент можно оставить только в наблюдении.",
            "is_buy_candidate": False,
        }

    if ml_adjustment is not None and ml_adjustment <= -10 and probability_value < 45:
        return {
            "action": "avoid_ml_filter",
            "recommendation": "Не покупать",
            "decision": "ML-фильтр снизил прогноз",
            "decision_level": "negative",
            "decision_reason": "ML-модель заметно снизила итоговую вероятность, поэтому сигнал не проходит потребительский фильтр.",
            "is_buy_candidate": False,
        }

    if probability_value >= 65 and is_high_reliability:
        return {
            "action": "buy",
            "recommendation": "Покупать",
            "decision": "Сильный сигнал",
            "decision_level": "positive",
            "decision_reason": "Вероятность высокая, надёжность достаточная, риск-фильтр пройден.",
            "is_buy_candidate": True,
        }

    if probability_value >= 58 and (is_high_reliability or is_medium_reliability):
        return {
            "action": "consider_buy",
            "recommendation": "Рассмотреть покупку",
            "decision": "Умеренно положительный сигнал",
            "decision_level": "positive",
            "decision_reason": "Вероятность выше среднего, но сигнал требует контроля риска и размера позиции.",
            "is_buy_candidate": True,
        }

    if probability_value >= 45:
        return {
            "action": "watch",
            "recommendation": "Наблюдать",
            "decision": "Нейтральный сигнал",
            "decision_level": "neutral",
            "decision_reason": "Вероятность недостаточна для покупки, но инструмент стоит оставить в наблюдении.",
            "is_buy_candidate": False,
        }

    if ml_probability is not None and 35 <= ml_probability < 45 and probability_value >= 40:
        return {
            "action": "watch_ml_confirmed",
            "recommendation": "Наблюдать",
            "decision": "Есть ML-подтверждение, но итоговая вероятность пока низкая",
            "decision_level": "neutral",
            "decision_reason": "ML находится в рабочей зоне 35–45%, где walk-forward validation показал стабильный lift, но итоговый consumer score ещё не дотягивает до покупки.",
            "is_buy_candidate": False,
        }

    return {
        "action": "avoid",
        "recommendation": "Не покупать",
        "decision": "Слабый сигнал",
        "decision_level": "negative",
        "decision_reason": "Итоговая вероятность ниже минимального порога для потребительского сигнала.",
        "is_buy_candidate": False,
    }



def _build_position_sizing(
    *,
    action: str | None,
    price: float | None,
    target_price: float | None,
    stop_loss: float | None,
    probability: float | None,
    risk_level: str | None,
    reliability_level: str | None,
    reliability_score: float | None,
    ml_probability: float | None,
    ml_regime_multiplier: float | None,
    volatility_pct: float | None,
) -> dict[str, Any]:
    """Risk-adjusted position sizing for consumer signals.

    This is not portfolio optimization. It is a conservative risk layer that
    limits position size based on action quality, stop distance, reliability,
    ML confirmation and volatility.
    """

    normalized_action = str(action or "").strip()
    risk_text = str(risk_level or "").lower()
    reliability_text = str(reliability_level or "").lower()

    no_entry_actions = {
        "avoid",
        "avoid_ml_filter",
        "avoid_ml_veto",
        "avoid_risk",
        "no_forecast",
        "no_data",
        "no_price",
        "watch",
        "watch_ml_confirmed",
        "watch_ml_rejected",
    }

    if normalized_action in no_entry_actions:
        return {
            "allowed": False,
            "position_action": "no_entry" if normalized_action.startswith("avoid") else "watch_only",
            "max_position_pct": 0.0,
            "risk_per_trade_pct": 0.0,
            "stop_loss": _round(stop_loss),
            "stop_distance_pct": None,
            "target_price": _round(target_price),
            "target_distance_pct": _round(_pct_change(target_price, price)),
            "risk_reward_ratio": None,
            "reason": "Вход запрещён или разрешено только наблюдение по текущему consumer decision gate.",
            "risk_flags": [f"action={normalized_action}"],
        }

    if normalized_action == "buy":
        base_position_pct = 6.0
        base_risk_pct = 1.0
        position_action = "buy"
    elif normalized_action == "consider_buy":
        base_position_pct = 3.5
        base_risk_pct = 0.65
        position_action = "starter_position"
    else:
        return {
            "allowed": False,
            "position_action": "watch_only",
            "max_position_pct": 0.0,
            "risk_per_trade_pct": 0.0,
            "stop_loss": _round(stop_loss),
            "stop_distance_pct": None,
            "target_price": _round(target_price),
            "target_distance_pct": _round(_pct_change(target_price, price)),
            "risk_reward_ratio": None,
            "reason": "Для текущего действия позиция не открывается.",
            "risk_flags": [f"action={normalized_action}"],
        }

    risk_flags: list[str] = []
    factor = 1.0

    if "выс" in risk_text or "high" in risk_text or "risk" in risk_text or "риск" in risk_text:
        factor *= 0.55
        risk_flags.append("высокий риск сценария")
    elif "сред" in risk_text or "medium" in risk_text:
        factor *= 0.85
        risk_flags.append("средний риск сценария")

    if "низ" in reliability_text or "low" in reliability_text:
        factor *= 0.60
        risk_flags.append("низкая надёжность прогноза")
    elif "выс" in reliability_text or "high" in reliability_text:
        factor *= 1.08

    score = _to_float(reliability_score)
    if score is not None:
        if score < 45:
            factor *= 0.65
            risk_flags.append("низкий reliability_score")
        elif score >= 75:
            factor *= 1.05

    ml_value = _to_float(ml_probability)
    if ml_value is not None:
        if ml_value < 25:
            factor *= 0.50
            risk_flags.append("ML ниже 25%")
        elif ml_value < 35:
            factor *= 0.80
            risk_flags.append("ML не даёт полноценного подтверждения")
        elif 35 <= ml_value < 45:
            factor *= 1.05
        else:
            factor *= 0.95

    regime = _to_float(ml_regime_multiplier)
    if regime is not None:
        if regime >= 1.15:
            factor *= 1.08
        elif regime < 1.0:
            factor *= 0.90
            risk_flags.append("режим не усиливает ML")

    vol = _to_float(volatility_pct)
    if vol is not None:
        if vol >= 4.0:
            factor *= 0.60
            risk_flags.append("повышенная волатильность")
        elif vol >= 2.8:
            factor *= 0.80
            risk_flags.append("умеренно высокая волатильность")

    derived_stop = False
    stop_value = _to_float(stop_loss)

    if price is not None and price > 0 and (stop_value is None or stop_value >= price):
        default_stop_pct = min(max((vol or 2.0) * 1.8, 2.5), 8.0)
        stop_value = price * (1 - default_stop_pct / 100)
        derived_stop = True
        risk_flags.append("стоп рассчитан автоматически")

    stop_distance_pct = None
    target_distance_pct = _pct_change(target_price, price)
    risk_reward_ratio = None

    if price is not None and price > 0 and stop_value is not None and stop_value < price:
        stop_distance_pct = (price - stop_value) / price * 100

    if (
        stop_distance_pct is not None
        and stop_distance_pct > 0
        and target_distance_pct is not None
        and target_distance_pct > 0
    ):
        risk_reward_ratio = target_distance_pct / stop_distance_pct

        if risk_reward_ratio < 0.8:
            factor *= 0.45
            risk_flags.append("слабое соотношение цель/риск")
        elif risk_reward_ratio < 1.2:
            factor *= 0.70
            risk_flags.append("умеренное соотношение цель/риск")
        elif risk_reward_ratio >= 2.0:
            factor *= 1.08

    position_cap_pct = base_position_pct * factor
    risk_per_trade_pct = base_risk_pct * min(factor, 1.0)

    if stop_distance_pct is not None and stop_distance_pct > 0:
        max_by_risk_pct = risk_per_trade_pct / stop_distance_pct * 100
        position_cap_pct = min(position_cap_pct, max_by_risk_pct)

    position_cap_pct = max(0.25, min(position_cap_pct, 7.0))
    risk_per_trade_pct = max(0.10, min(risk_per_trade_pct, 1.0))

    reason_parts = [
        f"Базовый режим: {position_action}.",
        f"Размер позиции ограничен до {position_cap_pct:.2f}% портфеля.",
        f"Риск на сделку: {risk_per_trade_pct:.2f}% портфеля.",
    ]

    if risk_flags:
        reason_parts.append("Факторы снижения: " + "; ".join(risk_flags[:5]) + ".")

    return {
        "allowed": True,
        "position_action": position_action,
        "max_position_pct": _round(position_cap_pct, 2),
        "risk_per_trade_pct": _round(risk_per_trade_pct, 2),
        "stop_loss": _round(stop_value),
        "stop_source": "derived" if derived_stop else "signal",
        "stop_distance_pct": _round(stop_distance_pct, 2),
        "target_price": _round(target_price),
        "target_distance_pct": _round(target_distance_pct, 2),
        "risk_reward_ratio": _round(risk_reward_ratio, 2),
        "reason": " ".join(reason_parts),
        "risk_flags": risk_flags,
    }

def build_consumer_forecast(
    ticker: str,
    instrument: dict[str, Any],
    latest: dict[str, Any],
    technical: dict[str, Any],
    candles: list[dict[str, Any]],
    signal: dict[str, Any],
    events: list[dict[str, Any]],
    ml_probability_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    price = _to_float(latest.get("close"))
    regime_features = _build_consumer_regime_features(candles)
    target_price = _derive_target_price(price, signal, technical)
    forecast_range = _derive_forecast_range(price, target_price, signal, technical)
    stop_loss_value = _to_float(signal.get("stop_loss"))
    rule_probability = _calculate_target_probability(signal, technical, price, target_price, events)
    ml_probability = (
        _to_float((ml_probability_result or {}).get("ml_probability_pct"))
        if ml_probability_result and ml_probability_result.get("ok")
        else None
    )

    probability_blend = _blend_rule_and_ml_probability(
        rule_probability=rule_probability,
        ml_probability=ml_probability,
        regime=regime_features,
    )
    base_probability = probability_blend.get("probability")
    probability_source = probability_blend.get("source")
    ml_weight = probability_blend.get("ml_weight")
    ml_adjustment_pct = probability_blend.get("ml_adjustment_pct")
    regime_multiplier, regime_reason = _regime_ml_multiplier(regime_features)

    probability_assessment = build_probability_assessment(
        base_probability_pct=base_probability,
        candles=candles,
        signal=signal,
        technical=technical,
        price=price,
        target_price=target_price,
        stop_loss=stop_loss_value,
        events=events,
        horizon_days=20,
    )
    probability = probability_assessment.get("probability_pct")

    preliminary_target_distance_pct = _pct_change(target_price, price)
    preliminary_stop_distance_pct = None

    if price is not None and price > 0 and stop_loss_value is not None and stop_loss_value < price:
        preliminary_stop_distance_pct = (price - stop_loss_value) / price * 100

    preliminary_risk_reward_ratio = (
        preliminary_target_distance_pct / preliminary_stop_distance_pct
        if preliminary_target_distance_pct is not None
        and preliminary_target_distance_pct > 0
        and preliminary_stop_distance_pct is not None
        and preliminary_stop_distance_pct > 0
        else None
    )

    decision_gate = _consumer_signal_decision_gate(
        probability=probability,
        reliability_level=probability_assessment.get("reliability_level"),
        risk_level=signal.get("risk_level"),
        ml_adjustment_pct=ml_adjustment_pct,
        ml_probability_pct=ml_probability,
        risk_reward_ratio=preliminary_risk_reward_ratio,
        target_distance_pct=preliminary_target_distance_pct,
    )
    recommendation, tone = _recommendation_from_action(signal.get("action"), probability)

    potential_pct = _round(_pct_change(target_price, price))
    potential_abs = _round(target_price - price) if price is not None and target_price is not None else None

    if signal.get("action") == "risk_sell_watch":
        forecast_price = forecast_range.get("low") or target_price
    elif signal.get("action") in {"buy_watch", "watch_buy"}:
        forecast_price = target_price
    else:
        high = _to_float(forecast_range.get("high"))
        low = _to_float(forecast_range.get("low"))
        forecast_price = _round((high + low) / 2) if high is not None and low is not None else target_price

    position_sizing = _build_position_sizing(
        action=decision_gate.get("action"),
        price=price,
        target_price=target_price,
        stop_loss=stop_loss_value,
        probability=probability,
        risk_level=signal.get("risk_level"),
        reliability_level=probability_assessment.get("reliability_level"),
        reliability_score=probability_assessment.get("reliability_score"),
        ml_probability=ml_probability,
        ml_regime_multiplier=regime_multiplier,
        volatility_pct=_to_float(technical.get("volatility_20d_pct")),
    )

    # Preserve RR diagnostics even when entry is blocked by decision gate.
    if preliminary_target_distance_pct is not None and position_sizing.get("target_distance_pct") is None:
        position_sizing["target_distance_pct"] = _round(preliminary_target_distance_pct, 2)

    if preliminary_stop_distance_pct is not None and position_sizing.get("stop_distance_pct") is None:
        position_sizing["stop_distance_pct"] = _round(preliminary_stop_distance_pct, 2)

    if preliminary_risk_reward_ratio is not None and position_sizing.get("risk_reward_ratio") is None:
        position_sizing["risk_reward_ratio"] = _round(preliminary_risk_reward_ratio, 2)

    return {
        "ticker": ticker,
        "name": instrument.get("name") or ticker,
        "sector": instrument.get("sector"),
        "asset_type": instrument.get("asset_type"),
        "is_signal_eligible": instrument.get("is_signal_eligible"),
        "price": _round(price),
        "trade_date": latest.get("trade_date"),
        "recommendation": decision_gate.get("recommendation") or recommendation,
        "decision": decision_gate.get("decision"),
        "decision_level": decision_gate.get("decision_level"),
        "decision_reason": decision_gate.get("decision_reason"),
        "is_buy_candidate": decision_gate.get("is_buy_candidate"),
        "recommendation_tone": tone,
        "action": decision_gate.get("action") or signal.get("action"),
        "target_price": _round(target_price),
        "forecast_price": _round(forecast_price),
        "forecast_range": forecast_range,
        "potential_abs": potential_abs,
        "potential_pct": potential_pct,
        "target_probability_pct": probability,
        "base_probability_pct": probability_assessment.get("base_probability_pct"),
        "rule_probability_pct": _round(rule_probability, 1),
        "ml_probability_pct": _round(ml_probability, 1),
        "ml_weight": ml_weight,
        "ml_adjustment_pct": ml_adjustment_pct,
        "probability_source": probability_source,
        "ml_regime_multiplier": regime_multiplier,
        "ml_regime_reason": regime_reason,
        "consumer_action": decision_gate.get("action"),
        "recommendation": decision_gate.get("recommendation"),
        "decision": decision_gate.get("decision"),
        "decision_level": decision_gate.get("decision_level"),
        "decision_reason": decision_gate.get("decision_reason"),
        "is_buy_candidate": decision_gate.get("is_buy_candidate"),
        "horizon": signal.get("horizon") or "1–4 недели",
        "risk_level": signal.get("risk_level"),
        "reliability_level": probability_assessment.get("reliability_level"),
        "reliability_score": probability_assessment.get("reliability_score"),
        "stop_loss": _round(position_sizing.get("stop_loss")),
        "position_sizing": position_sizing,
        "risk_reward_ratio": position_sizing.get("risk_reward_ratio"),
        "explanation": _build_explanation(
            signal,
            technical,
            events,
            probability,
            probability_assessment,
            ml_probability_result=ml_probability_result,
        ),
        "probability_assessment": probability_assessment,
        "events": events,
        "internal": {
            "engine": CONSUMER_SIGNAL_MODEL_VERSION,
            "confidence_pct": _round(signal.get("confidence_pct"), 0),
            "quality_score": _round(signal.get("quality_score"), 0),
            "risk_reward_ratio": _round(signal.get("risk_reward_ratio"), 2),
        },
    }



def _instrument_to_consumer_dict(instrument: Instrument | None, ticker: str) -> dict[str, Any]:
    if instrument is None:
        return {
            "ticker": ticker,
            "name": ticker,
            "asset_type": "unknown",
            "is_signal_eligible": False,
        }

    return {
        "ticker": instrument.ticker,
        "name": instrument.name or instrument.ticker,
        "board": instrument.board,
        "sector": instrument.sector,
        "asset_type": getattr(instrument, "asset_type", "unknown") or "unknown",
        "is_signal_eligible": bool(getattr(instrument, "is_signal_eligible", False)),
        "lot_size": instrument.lot_size,
    }


def _unsupported_forecast_response(
    ticker: str,
    instrument: dict[str, Any],
    reason: str,
    message: str,
) -> dict[str, Any]:
    return {
        "ok": False,
        "ticker": ticker,
        "reason": reason,
        "message": message,
        "instrument": instrument,
        "forecast": None,
        "signal": {
            "recommendation": "Недостаточно данных",
            "target_probability_pct": None,
            "target_price": None,
            "forecast_range": {"low": None, "high": None},
            "horizon": None,
            "risk_level": "unknown",
            "reliability_level": "Низкая",
            "reliability_score": 0,
            "explanation": {
                "summary": message,
                "technical": ["Прогноз не построен, потому что инструмент не проходит базовые условия модели."],
                "news": ["Новостной фон не анализировался для неподдерживаемого прогноза."],
                "risks": ["Система не должна выдавать вероятность там, где модель неприменима или данных недостаточно."],
            },
        },
    }


def _get_consumer_instrument(db: Session, ticker: str) -> Instrument | None:
    return db.scalar(select(Instrument).where(Instrument.ticker == ticker))


def _get_candles_count(db: Session, ticker: str) -> int:
    return int(db.scalar(select(func.count(Candle.id)).where(Candle.ticker == ticker)) or 0)


def build_consumer_signal_for_ticker(
    db: Session,
    ticker: str,
    candles_limit: int = 240,
) -> dict[str, Any]:
    ticker = ticker.upper().strip()

    db_instrument = _get_consumer_instrument(db=db, ticker=ticker)
    instrument_meta = _instrument_to_consumer_dict(db_instrument, ticker)

    if db_instrument is None:
        return _unsupported_forecast_response(
            ticker=ticker,
            instrument=instrument_meta,
            reason="instrument_not_found",
            message="Инструмент не найден в локальном справочнике MOEX. Обновите universe или проверьте тикер.",
        )

    if not instrument_meta.get("is_signal_eligible"):
        asset_type = instrument_meta.get("asset_type") or "unknown"
        return _unsupported_forecast_response(
            ticker=ticker,
            instrument=instrument_meta,
            reason="unsupported_asset_type",
            message=f"Для типа инструмента '{asset_type}' потребительский прогноз пока не строится.",
        )

    candles_count = _get_candles_count(db=db, ticker=ticker)
    if candles_count < 60:
        return _unsupported_forecast_response(
            ticker=ticker,
            instrument=instrument_meta,
            reason="not_enough_candles",
            message=f"Недостаточно исторических данных для прогноза: найдено {candles_count} свечей, нужно минимум 60.",
        )

    snapshot = get_ticker_snapshot(
        db=db,
        ticker=ticker,
        limit=candles_limit,
    )

    latest = snapshot.get("latest") or {}
    technical = snapshot.get("technical") or {}
    fallback_signal = snapshot.get("signal") or {}
    instrument = {
        **instrument_meta,
        **(snapshot.get("instrument") or {"ticker": ticker, "name": ticker}),
        "asset_type": instrument_meta.get("asset_type"),
        "is_signal_eligible": instrument_meta.get("is_signal_eligible"),
    }
    candles = snapshot.get("candles") or []

    # Дополняем технический блок ближайшими максимумами/минимумами, чтобы прогноз имел диапазон.
    recent = candles[-20:] if candles else []
    highs = [_to_float(row.get("high")) for row in recent]
    lows = [_to_float(row.get("low")) for row in recent]
    highs = [value for value in highs if value is not None]
    lows = [value for value in lows if value is not None]
    technical = dict(technical)
    if highs and technical.get("recent_high") is None:
        technical["recent_high"] = round(max(highs), 2)
    if lows and technical.get("recent_low") is None:
        technical["recent_low"] = round(min(lows), 2)

    signal = _build_unified_signal(
        candles=candles,
        latest=latest,
        technical=technical,
        fallback_signal=fallback_signal,
    )

    events = list_related_events(db=db, ticker=ticker, limit=3)

    try:
        ml_probability_result = predict_ml_probability_for_ticker(
            db=db,
            ticker=ticker,
            min_history=60,
        )
    except Exception as exc:  # noqa: BLE001
        ml_probability_result = {
            "ok": False,
            "reason": "ml_prediction_error",
            "message": str(exc),
        }

    forecast = build_consumer_forecast(
        ticker=ticker,
        instrument=instrument,
        latest=latest,
        technical=technical,
        candles=candles,
        signal=signal,
        events=events,
        ml_probability_result=ml_probability_result,
    )

    return {
        "ok": True,
        "ticker": ticker,
        "forecast": forecast,
        "signal": {
            "recommendation": forecast.get("recommendation"),
            "target_probability_pct": forecast.get("target_probability_pct"),
            "rule_probability_pct": forecast.get("rule_probability_pct"),
            "ml_probability_pct": forecast.get("ml_probability_pct"),
            "ml_weight": forecast.get("ml_weight"),
            "ml_adjustment_pct": forecast.get("ml_adjustment_pct"),
            "ml_regime_multiplier": forecast.get("ml_regime_multiplier"),
            "ml_regime_reason": forecast.get("ml_regime_reason"),
            "probability_source": forecast.get("probability_source"),
            "consumer_action": forecast.get("consumer_action"),
            "recommendation": forecast.get("recommendation"),
            "decision": forecast.get("decision"),
            "decision_level": forecast.get("decision_level"),
            "decision_reason": forecast.get("decision_reason"),
            "is_buy_candidate": forecast.get("is_buy_candidate"),
            "target_price": forecast.get("target_price"),
            "forecast_range": forecast.get("forecast_range"),
            "horizon": forecast.get("horizon"),
            "risk_level": forecast.get("risk_level"),
            "reliability_level": forecast.get("reliability_level"),
            "reliability_score": forecast.get("reliability_score"),
            "position_sizing": forecast.get("position_sizing"),
            "risk_reward_ratio": forecast.get("risk_reward_ratio"),
            "probability_assessment": forecast.get("probability_assessment"),
            "explanation": forecast.get("explanation"),
        },
    }


def list_consumer_signals(
    db: Session,
    limit: int = 100,
    action: str | None = None,
    min_probability: float | None = None,
    candles_limit: int = 240,
    q: str | None = None,
) -> dict[str, Any]:
    from app.services.market_universe import search_instruments

    query_text = (q or "").strip()

    search_result = search_instruments(
        db=db,
        q=query_text or None,
        limit=limit,
        only_with_candles=True,
        eligible_only=True,
    )
    tickers = [row.get("ticker") for row in search_result.get("rows") or [] if row.get("ticker")]
    rows: list[dict[str, Any]] = []

    for ticker in tickers:
        data = build_consumer_signal_for_ticker(
            db=db,
            ticker=ticker,
            candles_limit=candles_limit,
        )
        if not data.get("ok"):
            continue

        forecast = data.get("forecast") or {}

        if action and forecast.get("action") != action:
            continue

        probability = _to_float(forecast.get("target_probability_pct"))
        if min_probability is not None and (probability is None or probability < min_probability):
            continue

        rows.append(
            {
                "ticker": ticker,
                "name": forecast.get("name") or ticker,
                "price": forecast.get("price"),
                "trade_date": forecast.get("trade_date"),
                "recommendation": forecast.get("recommendation"),
                "recommendation_tone": forecast.get("recommendation_tone"),
                "action": forecast.get("action"),
                "consumer_action": forecast.get("consumer_action"),
                "decision": forecast.get("decision"),
                "decision_level": forecast.get("decision_level"),
                "decision_reason": forecast.get("decision_reason"),
                "is_buy_candidate": forecast.get("is_buy_candidate"),
                "target_probability_pct": forecast.get("target_probability_pct"),
                "rule_probability_pct": forecast.get("rule_probability_pct"),
                "ml_probability_pct": forecast.get("ml_probability_pct"),
                "ml_weight": forecast.get("ml_weight"),
                "ml_adjustment_pct": forecast.get("ml_adjustment_pct"),
                "ml_regime_multiplier": forecast.get("ml_regime_multiplier"),
                "ml_regime_reason": forecast.get("ml_regime_reason"),
                "probability_source": forecast.get("probability_source"),
                "target_price": forecast.get("target_price"),
                "forecast_price": forecast.get("forecast_price"),
                "forecast_range": forecast.get("forecast_range"),
                "potential_abs": forecast.get("potential_abs"),
                "potential_pct": forecast.get("potential_pct"),
                "horizon": forecast.get("horizon"),
                "risk_level": forecast.get("risk_level"),
                "reliability_level": forecast.get("reliability_level"),
                "reliability_score": forecast.get("reliability_score"),
                "position_sizing": forecast.get("position_sizing"),
                "risk_reward_ratio": forecast.get("risk_reward_ratio"),
                "explanation": forecast.get("explanation"),
                "ticker_url": f"/tickers/{ticker}",
            }
        )

    rows.sort(
        key=lambda row: (
            ACTION_RANK.get(row.get("action"), 99),
            -float(row.get("target_probability_pct") or 0),
            row.get("ticker") or "",
        )
    )

    positive_actions = {"buy", "consider_buy", "buy_watch", "watch_buy"}
    watch_actions = {"watch", "watch_ml_confirmed", "watch_ml_rejected", "watch_bad_rr", "hold_watch"}
    risk_actions = {"avoid", "avoid_bad_target", "avoid_bad_rr", "avoid_ml_filter", "avoid_ml_veto", "avoid_risk", "risk_sell_watch"}

    summary = {
        "total": len(rows),
        "positive": sum(1 for row in rows if row.get("action") in positive_actions),
        "watch": sum(1 for row in rows if row.get("action") in watch_actions),
        "risk": sum(1 for row in rows if row.get("action") in risk_actions),
        "buy": sum(1 for row in rows if row.get("action") == "buy"),
        "consider_buy": sum(1 for row in rows if row.get("action") == "consider_buy"),
        "watch_ml_confirmed": sum(1 for row in rows if row.get("action") == "watch_ml_confirmed"),
        "avoid_ml_filter": sum(1 for row in rows if row.get("action") == "avoid_ml_filter"),
        "avoid_ml_veto": sum(1 for row in rows if row.get("action") == "avoid_ml_veto"),
        "avoid_bad_target": sum(1 for row in rows if row.get("action") == "avoid_bad_target"),
        "avoid_bad_rr": sum(1 for row in rows if row.get("action") == "avoid_bad_rr"),
        "watch_bad_rr": sum(1 for row in rows if row.get("action") == "watch_bad_rr"),
        "watch_ml_rejected": sum(1 for row in rows if row.get("action") == "watch_ml_rejected"),
        "avg_probability_pct": _round(
            sum(float(row.get("target_probability_pct") or 0) for row in rows) / len(rows),
            1,
        ) if rows else None,
    }

    return {
        "ok": True,
        "mode": "consumer",
        "summary": summary,
        "rows": rows,
        "notes": [
            "Страница не показывает выбор модели: используется единый потребительский прогноз.",
            "Вероятность — это оценка достижения указанной цели в заданном горизонте, а не гарантия результата.",
        ],
    }

# --- Ticker alias resolver wrapper ---
from app.services.ticker_aliases import apply_alias_metadata, resolve_ticker_alias

_build_consumer_signal_for_ticker_without_alias = build_consumer_signal_for_ticker


def build_consumer_signal_for_ticker(
    db: Session,
    ticker: str,
    candles_limit: int = 240,
) -> dict[str, Any]:
    resolution = resolve_ticker_alias(ticker)
    result = _build_consumer_signal_for_ticker_without_alias(
        db=db,
        ticker=resolution["resolved_ticker"],
        candles_limit=candles_limit,
    )

    if isinstance(result, dict):
        apply_alias_metadata(result, resolution)

    return result


_ALIAS_AWARE_CONSUMER_SIGNAL_WRAPPER = True

