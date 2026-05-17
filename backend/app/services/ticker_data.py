from __future__ import annotations

from datetime import date, datetime
from statistics import pstdev
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Candle, Instrument


def _json_value(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()

    return value


def _get_attr(obj: Any, names: list[str], default: Any = None) -> Any:
    for name in names:
        if hasattr(obj, name):
            value = getattr(obj, name)
            if value is not None:
                return value

    return default


def _to_float(value: Any) -> float | None:
    try:
        if value is None:
            return None

        return float(value)
    except Exception:
        return None


def _round(value: Any, digits: int = 2) -> float | None:
    number = _to_float(value)

    if number is None:
        return None

    return round(number, digits)


def _avg(values: list[float]) -> float | None:
    clean = [float(v) for v in values if v is not None]

    if not clean:
        return None

    return sum(clean) / len(clean)


def _pct_change(current: float | None, previous: float | None) -> float | None:
    if current is None or previous in (None, 0):
        return None

    return (current - previous) / previous * 100


def candle_to_dict(candle: Candle) -> dict[str, Any]:
    return {
        "ticker": _get_attr(candle, ["ticker"], ""),
        "board": _get_attr(candle, ["board"], ""),
        "trade_date": _json_value(_get_attr(candle, ["trade_date", "date", "begin"], "")),
        "open": _round(_get_attr(candle, ["open"])),
        "high": _round(_get_attr(candle, ["high"])),
        "low": _round(_get_attr(candle, ["low"])),
        "close": _round(_get_attr(candle, ["close", "last", "price"])),
        "previous_close": _round(_get_attr(candle, ["previous_close", "prev_close"])),
        "change_abs": None,
        "change_pct": None,
        "volume": _round(_get_attr(candle, ["volume", "vol"], 0), 0),
        "value_rub": _round(_get_attr(candle, ["value_rub", "value", "turnover"], 0), 2),
    }


def enrich_candles_with_changes(candles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    previous_close = None

    for candle in candles:
        close = _to_float(candle.get("close"))

        if candle.get("previous_close") in (None, 0) and previous_close not in (None, 0):
            candle["previous_close"] = round(previous_close, 2)

        prev = _to_float(candle.get("previous_close"))

        if close is not None and prev not in (None, 0):
            candle["change_abs"] = round(close - prev, 2)
            candle["change_pct"] = round((close - prev) / prev * 100, 2)

        if close is not None:
            previous_close = close

    return candles


def build_technical_snapshot(candles: list[dict[str, Any]]) -> dict[str, Any]:
    closes = [_to_float(row.get("close")) for row in candles]
    closes = [value for value in closes if value is not None]

    volumes = [_to_float(row.get("volume")) for row in candles]
    volumes = [value for value in volumes if value is not None]

    if not closes:
        return {
            "ok": False,
            "summary": "Недостаточно данных для технической картины.",
        }

    latest_close = closes[-1]

    sma_20 = _avg(closes[-20:]) if len(closes) >= 20 else None
    sma_50 = _avg(closes[-50:]) if len(closes) >= 50 else None

    return_1d_pct = _pct_change(latest_close, closes[-2]) if len(closes) >= 2 else None
    return_5d_pct = _pct_change(latest_close, closes[-6]) if len(closes) >= 6 else None
    return_20d_pct = _pct_change(latest_close, closes[-21]) if len(closes) >= 21 else None

    daily_returns = []
    for index in range(1, len(closes)):
        change = _pct_change(closes[index], closes[index - 1])
        if change is not None:
            daily_returns.append(change)

    volatility_20d_pct = None
    if len(daily_returns) >= 5:
        volatility_20d_pct = pstdev(daily_returns[-20:])

    avg_volume_20 = _avg(volumes[-20:]) if len(volumes) >= 20 else _avg(volumes)
    latest_volume = volumes[-1] if volumes else None

    volume_ratio = None
    if latest_volume is not None and avg_volume_20 not in (None, 0):
        volume_ratio = latest_volume / avg_volume_20

    distance_to_sma_20_pct = _pct_change(latest_close, sma_20)
    distance_to_sma_50_pct = _pct_change(latest_close, sma_50)

    if sma_20 is not None and sma_50 is not None:
        if latest_close > sma_20 > sma_50:
            trend = "восходящий тренд"
        elif latest_close < sma_20 < sma_50:
            trend = "нисходящий тренд"
        elif latest_close > sma_20:
            trend = "цена выше SMA20, но тренд смешанный"
        elif latest_close < sma_20:
            trend = "цена ниже SMA20, тренд смешанный"
        else:
            trend = "нейтрально"
    elif sma_20 is not None:
        trend = "цена выше SMA20" if latest_close > sma_20 else "цена ниже SMA20"
    else:
        trend = "недостаточно данных для SMA"

    parts = [f"Техническая картина: {trend}."]

    if return_5d_pct is not None:
        direction = "рост" if return_5d_pct > 0 else "снижение" if return_5d_pct < 0 else "без изменения"
        parts.append(f"За последние 5 свечей: {direction} на {round(return_5d_pct, 2)}%.")

    if distance_to_sma_20_pct is not None:
        parts.append(f"Цена отклоняется от SMA20 на {round(distance_to_sma_20_pct, 2)}%.")

    if volume_ratio is not None:
        if volume_ratio >= 1.5:
            parts.append("Объём заметно выше среднего.")
        elif volume_ratio <= 0.7:
            parts.append("Объём ниже среднего.")
        else:
            parts.append("Объём около среднего уровня.")

    return {
        "ok": True,
        "latest_close": round(latest_close, 2),
        "sma_20": _round(sma_20),
        "sma_50": _round(sma_50),
        "return_1d_pct": _round(return_1d_pct),
        "return_5d_pct": _round(return_5d_pct),
        "return_20d_pct": _round(return_20d_pct),
        "volatility_20d_pct": _round(volatility_20d_pct),
        "avg_volume_20": _round(avg_volume_20, 0),
        "volume_ratio": _round(volume_ratio, 2),
        "distance_to_sma_20_pct": _round(distance_to_sma_20_pct),
        "distance_to_sma_50_pct": _round(distance_to_sma_50_pct),
        "trend": trend,
        "summary": " ".join(parts),
    }



def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def build_ticker_signal(
    candles: list[dict[str, Any]],
    technical: dict[str, Any],
) -> dict[str, Any]:
    if not candles or not technical.get("ok"):
        return {
            "ok": False,
            "action": "no_data",
            "label": "Недостаточно данных",
            "summary": "Недостаточно данных для первичного сигнала.",
            "reasons": [],
        }

    latest = candles[-1]

    close = _to_float(latest.get("close"))
    sma_20 = _to_float(technical.get("sma_20"))
    sma_50 = _to_float(technical.get("sma_50"))
    return_5d_pct = _to_float(technical.get("return_5d_pct"))
    return_20d_pct = _to_float(technical.get("return_20d_pct"))
    volatility_20d_pct = _to_float(technical.get("volatility_20d_pct"))
    volume_ratio = _to_float(technical.get("volume_ratio"))

    if close is None:
        return {
            "ok": False,
            "action": "no_price",
            "label": "Нет цены",
            "summary": "Нет последней цены для расчёта сигнала.",
            "reasons": [],
        }

    recent = candles[-20:] if len(candles) >= 20 else candles

    highs = [_to_float(row.get("high")) for row in recent]
    lows = [_to_float(row.get("low")) for row in recent]

    highs = [value for value in highs if value is not None]
    lows = [value for value in lows if value is not None]

    recent_high = max(highs) if highs else close
    recent_low = min(lows) if lows else close

    score = 50.0
    reasons: list[str] = []

    if sma_20 is not None:
        if close > sma_20:
            score += 8
            reasons.append("Цена выше SMA20.")
        else:
            score -= 8
            reasons.append("Цена ниже SMA20.")

    if sma_20 is not None and sma_50 is not None:
        if sma_20 > sma_50:
            score += 8
            reasons.append("SMA20 выше SMA50 — среднесрочная структура позитивная.")
        else:
            score -= 8
            reasons.append("SMA20 ниже SMA50 — среднесрочная структура слабая.")

    if return_5d_pct is not None:
        if return_5d_pct >= 1:
            score += 7
            reasons.append(f"Положительный импульс за 5 свечей: {round(return_5d_pct, 2)}%.")
        elif return_5d_pct <= -1:
            score -= 7
            reasons.append(f"Отрицательный импульс за 5 свечей: {round(return_5d_pct, 2)}%.")
        else:
            reasons.append("Импульс за 5 свечей умеренный.")

    if return_20d_pct is not None:
        if return_20d_pct >= 3:
            score += 5
            reasons.append(f"Цена выросла за 20 свечей на {round(return_20d_pct, 2)}%.")
        elif return_20d_pct <= -3:
            score -= 5
            reasons.append(f"Цена снизилась за 20 свечей на {round(return_20d_pct, 2)}%.")

    if volume_ratio is not None:
        if volume_ratio >= 1.5:
            score += 4
            reasons.append(f"Объём выше среднего: {round(volume_ratio, 2)}x.")
        elif volume_ratio <= 0.7:
            score -= 2
            reasons.append(f"Объём ниже среднего: {round(volume_ratio, 2)}x.")
        else:
            reasons.append(f"Объём около среднего: {round(volume_ratio, 2)}x.")

    confidence_pct = round(_clamp(score, 25, 80), 0)

    if volatility_20d_pct is None:
        risk_level = "не определён"
    elif volatility_20d_pct >= 2.5:
        risk_level = "высокий"
    elif volatility_20d_pct >= 1.2:
        risk_level = "средний"
    else:
        risk_level = "умеренный"

    # Базовые уровни. Это не гарантия, а технический сценарий.
    if confidence_pct >= 68:
        action = "buy_watch"
        label = "Кандидат на покупку"
        entry_price = round(max(close, recent_high), 2)
        target_price = round(entry_price * 1.04, 2)
        stop_loss = round(min(sma_20 or close * 0.97, close * 0.97), 2)
        horizon = "1–4 недели"
        summary = (
            "Есть технический сценарий роста. Покупку лучше рассматривать не как автоматическое действие, "
            "а как сценарий при удержании цены выше ключевых средних и подтверждении объёмом."
        )
    elif confidence_pct >= 58:
        action = "watch_buy"
        label = "Наблюдать в сторону покупки"
        entry_price = round(recent_high, 2)
        target_price = round(recent_high * 1.03, 2)
        stop_loss = round(min(sma_20 or close * 0.97, close * 0.97), 2)
        horizon = "1–3 недели"
        summary = (
            "Картина умеренно позитивная, но сигнал требует подтверждения. "
            "Ключевой сценарий — закрепление выше ближайшего максимума."
        )
    elif confidence_pct <= 38:
        action = "risk_sell_watch"
        label = "Сигнал слабости / риск снижения"
        entry_price = None
        target_price = round(recent_low, 2)
        stop_loss = round(max(sma_20 or close * 1.03, close * 1.03), 2)
        horizon = "1–3 недели"
        summary = (
            "Техническая картина слабая. Для длинных позиций повышен риск просадки; "
            "лучше дождаться стабилизации или возврата выше средних."
        )
    else:
        action = "hold_watch"
        label = "Нейтрально / наблюдать"
        entry_price = None
        target_price = round(recent_high, 2)
        stop_loss = round(recent_low, 2)
        horizon = "1–3 недели"
        summary = (
            "Сигнал нейтральный. Явного преимущества для покупки или продажи по технике сейчас нет."
        )

    return {
        "ok": True,
        "action": action,
        "label": label,
        "entry_price": entry_price,
        "target_price": target_price,
        "stop_loss": stop_loss,
        "confidence_pct": confidence_pct,
        "risk_level": risk_level,
        "horizon": horizon,
        "recent_high": round(recent_high, 2),
        "recent_low": round(recent_low, 2),
        "summary": summary,
        "reasons": reasons,
        "disclaimer": "Первичный технический сигнал не является инвестиционной рекомендацией.",
    }

def get_instrument_info(
    db: Session,
    ticker: str,
) -> dict[str, Any]:
    ticker = ticker.upper().strip()

    row = db.scalars(
        select(Instrument)
        .where(Instrument.ticker == ticker)
        .limit(1)
    ).first()

    if row is None:
        return {
            "ticker": ticker,
            "name": ticker,
            "sector": None,
        }

    return {
        "ticker": ticker,
        "name": _get_attr(row, ["name", "short_name", "title"], ticker),
        "sector": _get_attr(row, ["sector", "industry"], None),
    }


def get_ticker_candles(
    db: Session,
    ticker: str,
    limit: int = 180,
) -> list[dict[str, Any]]:
    ticker = ticker.upper().strip()

    rows = db.scalars(
        select(Candle)
        .where(Candle.ticker == ticker)
        .order_by(Candle.trade_date.desc())
        .limit(limit)
    ).all()

    candles = [candle_to_dict(row) for row in rows]

    # Для графика удобнее хронологический порядок
    candles = list(reversed(candles))

    return enrich_candles_with_changes(candles)


def get_ticker_snapshot(
    db: Session,
    ticker: str,
    limit: int = 180,
) -> dict[str, Any]:
    ticker = ticker.upper().strip()

    instrument = get_instrument_info(
        db=db,
        ticker=ticker,
    )

    candles = get_ticker_candles(
        db=db,
        ticker=ticker,
        limit=limit,
    )

    latest = candles[-1] if candles else None
    technical = build_technical_snapshot(candles)
    signal = build_ticker_signal(candles, technical)

    return {
        "ticker": ticker,
        "instrument": instrument,
        "latest": latest,
        "technical": technical,
        "signal": signal,
        "candles": candles,
        "candles_count": len(candles),
        "auto_refresh_seconds": 60,
    }

# --- Ticker alias resolver wrapper ---
from typing import Any as _AliasAny

from app.services.ticker_aliases import apply_alias_metadata, resolve_ticker_alias

_get_ticker_snapshot_without_alias = get_ticker_snapshot


def get_ticker_snapshot(
    db,
    ticker: str,
    limit: int = 240,
) -> dict[str, _AliasAny]:
    resolution = resolve_ticker_alias(ticker)
    result = _get_ticker_snapshot_without_alias(
        db=db,
        ticker=resolution["resolved_ticker"],
        limit=limit,
    )

    if isinstance(result, dict):
        apply_alias_metadata(result, resolution)

    return result


_ALIAS_AWARE_TICKER_DATA_WRAPPER = True

