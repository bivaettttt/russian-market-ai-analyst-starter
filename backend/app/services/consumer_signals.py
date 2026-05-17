from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import MarketEvent
from app.services.ticker_data import get_ticker_snapshot
from app.services.consumer_probability import build_probability_assessment

CONSUMER_SIGNAL_MODEL_VERSION = "tech_v4_quality_rr"

ACTION_RANK = {
    "buy_watch": 1,
    "watch_buy": 2,
    "hold_watch": 3,
    "risk_sell_watch": 4,
    "no_data": 9,
    "no_price": 9,
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
    if explicit_target is not None:
        return round(explicit_target, 2)

    if price is None:
        return None

    action = signal.get("action")
    recent_high = _to_float(technical.get("recent_high"))
    recent_low = _to_float(technical.get("recent_low"))
    sma_20 = _to_float(technical.get("sma_20"))
    volatility = _to_float(technical.get("volatility_20d_pct")) or 1.5

    if action in {"buy_watch", "watch_buy"}:
        candidate = max(
            price * 1.035,
            recent_high or price,
            sma_20 or price,
        )
        return round(candidate, 2)

    if action == "risk_sell_watch":
        candidate = min(
            price * (1 - min(max(volatility, 1.0), 4.0) / 100 * 2),
            recent_low or price,
        )
        return round(candidate, 2)

    spread = min(max(volatility, 1.0), 3.5) / 100 * 1.5
    candidate = max(price * (1 + spread), recent_high or price)
    return round(candidate, 2)


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


def build_consumer_forecast(
    ticker: str,
    instrument: dict[str, Any],
    latest: dict[str, Any],
    technical: dict[str, Any],
    candles: list[dict[str, Any]],
    signal: dict[str, Any],
    events: list[dict[str, Any]],
) -> dict[str, Any]:
    price = _to_float(latest.get("close"))
    target_price = _derive_target_price(price, signal, technical)
    forecast_range = _derive_forecast_range(price, target_price, signal, technical)
    base_probability = _calculate_target_probability(signal, technical, price, target_price, events)
    probability_assessment = build_probability_assessment(
        base_probability_pct=base_probability,
        candles=candles,
        signal=signal,
        technical=technical,
        price=price,
        target_price=target_price,
        stop_loss=_to_float(signal.get("stop_loss")),
        events=events,
        horizon_days=20,
    )
    probability = probability_assessment.get("probability_pct")
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

    return {
        "ticker": ticker,
        "name": instrument.get("name") or ticker,
        "sector": instrument.get("sector"),
        "price": _round(price),
        "trade_date": latest.get("trade_date"),
        "recommendation": recommendation,
        "recommendation_tone": tone,
        "action": signal.get("action"),
        "target_price": _round(target_price),
        "forecast_price": _round(forecast_price),
        "forecast_range": forecast_range,
        "potential_abs": potential_abs,
        "potential_pct": potential_pct,
        "target_probability_pct": probability,
        "base_probability_pct": probability_assessment.get("base_probability_pct"),
        "horizon": signal.get("horizon") or "1–4 недели",
        "risk_level": signal.get("risk_level"),
        "reliability_level": probability_assessment.get("reliability_level"),
        "reliability_score": probability_assessment.get("reliability_score"),
        "stop_loss": _round(signal.get("stop_loss")),
        "explanation": _build_explanation(signal, technical, events, probability, probability_assessment),
        "probability_assessment": probability_assessment,
        "events": events,
        "internal": {
            "engine": CONSUMER_SIGNAL_MODEL_VERSION,
            "confidence_pct": _round(signal.get("confidence_pct"), 0),
            "quality_score": _round(signal.get("quality_score"), 0),
            "risk_reward_ratio": _round(signal.get("risk_reward_ratio"), 2),
        },
    }


def build_consumer_signal_for_ticker(
    db: Session,
    ticker: str,
    candles_limit: int = 240,
) -> dict[str, Any]:
    ticker = ticker.upper().strip()

    snapshot = get_ticker_snapshot(
        db=db,
        ticker=ticker,
        limit=candles_limit,
    )

    latest = snapshot.get("latest") or {}
    technical = snapshot.get("technical") or {}
    fallback_signal = snapshot.get("signal") or {}
    instrument = snapshot.get("instrument") or {"ticker": ticker, "name": ticker}
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

    forecast = build_consumer_forecast(
        ticker=ticker,
        instrument=instrument,
        latest=latest,
        technical=technical,
        candles=candles,
        signal=signal,
        events=events,
    )

    return {
        "ok": True,
        "ticker": ticker,
        "forecast": forecast,
        "signal": {
            "recommendation": forecast.get("recommendation"),
            "target_probability_pct": forecast.get("target_probability_pct"),
            "target_price": forecast.get("target_price"),
            "forecast_range": forecast.get("forecast_range"),
            "horizon": forecast.get("horizon"),
            "risk_level": forecast.get("risk_level"),
            "reliability_level": forecast.get("reliability_level"),
            "reliability_score": forecast.get("reliability_score"),
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
    from app.services.signals_data import list_market_tickers
    from app.services.market_universe import search_instruments

    query_text = (q or "").strip()

    if query_text:
        search_result = search_instruments(db=db, q=query_text, limit=limit, only_with_candles=True)
        tickers = [row.get("ticker") for row in search_result.get("rows") or [] if row.get("ticker")]
    else:
        tickers = list_market_tickers(db=db, limit=limit)
    rows: list[dict[str, Any]] = []

    for ticker in tickers:
        data = build_consumer_signal_for_ticker(
            db=db,
            ticker=ticker,
            candles_limit=candles_limit,
        )
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
                "target_probability_pct": forecast.get("target_probability_pct"),
                "target_price": forecast.get("target_price"),
                "forecast_price": forecast.get("forecast_price"),
                "forecast_range": forecast.get("forecast_range"),
                "potential_abs": forecast.get("potential_abs"),
                "potential_pct": forecast.get("potential_pct"),
                "horizon": forecast.get("horizon"),
                "risk_level": forecast.get("risk_level"),
                "reliability_level": forecast.get("reliability_level"),
                "reliability_score": forecast.get("reliability_score"),
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

    summary = {
        "total": len(rows),
        "positive": sum(1 for row in rows if row.get("action") in {"buy_watch", "watch_buy"}),
        "watch": sum(1 for row in rows if row.get("action") == "hold_watch"),
        "risk": sum(1 for row in rows if row.get("action") == "risk_sell_watch"),
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
