from __future__ import annotations

import math
from statistics import pstdev
from typing import Any

from sqlalchemy import asc, desc, distinct, select
from sqlalchemy.orm import Session

from app.models import Candle
from app.services.signals_evaluation import (
    evaluate_buy_signal,
    evaluate_neutral_signal,
    evaluate_risk_signal,
)
from app.services.ticker_data import candle_to_dict, enrich_candles_with_changes

SIGNAL_MODEL_VERSION = "tech_v1_sma_momentum"
TECH_V2_MODEL_VERSION = "tech_v2_rsi_atr"
TECH_V3_MODEL_VERSION = "tech_v3_v1_atr_risk"
TECH_V4_MODEL_VERSION = "tech_v4_quality_rr"
AVAILABLE_SIGNAL_MODEL_VERSIONS = {
    SIGNAL_MODEL_VERSION,
    TECH_V2_MODEL_VERSION,
    TECH_V3_MODEL_VERSION,
    TECH_V4_MODEL_VERSION,
}


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


def _pct_change(current: float | None, previous: float | None) -> float | None:
    if current is None or previous in (None, 0):
        return None
    return round((current - previous) / previous * 100, 2)


def _sma(values: list[float], period: int) -> float | None:
    if len(values) < period:
        return None
    return round(sum(values[-period:]) / period, 2)


def _volatility_pct(closes: list[float], period: int = 20) -> float | None:
    if len(closes) < period + 1:
        return None

    tail = closes[-period - 1:]
    returns = []

    for prev, curr in zip(tail, tail[1:]):
        if prev:
            returns.append((curr - prev) / prev * 100)

    if not returns:
        return None

    return round(pstdev(returns), 2)


def _avg(values: list[float]) -> float | None:
    clean = [v for v in values if v is not None]
    if not clean:
        return None
    return sum(clean) / len(clean)



def _rsi(closes: list[float], period: int = 14) -> float | None:
    if len(closes) < period + 1:
        return None

    gains: list[float] = []
    losses: list[float] = []

    tail = closes[-period - 1:]
    for prev, curr in zip(tail, tail[1:]):
        diff = curr - prev
        if diff >= 0:
            gains.append(diff)
            losses.append(0.0)
        else:
            gains.append(0.0)
            losses.append(abs(diff))

    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period

    if avg_loss == 0:
        return 100.0

    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)


def _atr(candles: list[dict[str, Any]], period: int = 14) -> float | None:
    if len(candles) < period + 1:
        return None

    true_ranges: list[float] = []
    tail = candles[-period - 1:]

    for prev, curr in zip(tail, tail[1:]):
        high = _to_float(curr.get("high"))
        low = _to_float(curr.get("low"))
        prev_close = _to_float(prev.get("close"))

        if high is None or low is None or prev_close is None:
            continue

        true_range = max(
            high - low,
            abs(high - prev_close),
            abs(low - prev_close),
        )
        true_ranges.append(true_range)

    if not true_ranges:
        return None

    return round(sum(true_ranges) / len(true_ranges), 2)

def build_historical_technical(candles: list[dict[str, Any]]) -> dict[str, Any]:
    closes = [_to_float(c.get("close")) for c in candles]
    closes = [c for c in closes if c is not None]

    volumes = [_to_float(c.get("volume")) for c in candles]
    volumes = [v for v in volumes if v is not None]

    latest = candles[-1] if candles else {}
    close = _to_float(latest.get("close"))

    sma_20 = _sma(closes, 20)
    sma_50 = _sma(closes, 50)

    return_1d = None
    if len(closes) >= 2:
        return_1d = _pct_change(closes[-1], closes[-2])

    return_5d = None
    if len(closes) >= 6:
        return_5d = _pct_change(closes[-1], closes[-6])

    return_20d = None
    if len(closes) >= 21:
        return_20d = _pct_change(closes[-1], closes[-21])

    volatility_20d = _volatility_pct(closes, 20)

    avg_volume_20 = _avg(volumes[-20:]) if volumes else None
    current_volume = _to_float(latest.get("volume"))

    volume_ratio = None
    if avg_volume_20 and current_volume is not None:
        volume_ratio = round(current_volume / avg_volume_20, 2)

    recent = candles[-20:] if len(candles) >= 20 else candles
    highs = [_to_float(c.get("high")) for c in recent]
    lows = [_to_float(c.get("low")) for c in recent]
    highs = [v for v in highs if v is not None]
    lows = [v for v in lows if v is not None]

    recent_high = max(highs) if highs else None
    recent_low = min(lows) if lows else None

    distance_to_sma_20_pct = _pct_change(close, sma_20)
    distance_to_sma_50_pct = _pct_change(close, sma_50)

    rsi_14 = _rsi(closes, 14)
    atr_14 = _atr(candles, 14)
    atr_pct = _pct_change((close or 0) + atr_14, close) if close is not None and atr_14 is not None else None

    trend = "нейтрально"

    if close is not None and sma_20 is not None and sma_50 is not None:
        if close > sma_20 and sma_20 > sma_50:
            trend = "восходящий тренд"
        elif close < sma_20 and sma_20 < sma_50:
            trend = "нисходящий тренд"
        elif close > sma_20:
            trend = "цена выше SMA20, но тренд смешанный"
        elif close < sma_20:
            trend = "цена ниже SMA20, но тренд смешанный"

    return {
        "close": close,
        "sma_20": sma_20,
        "sma_50": sma_50,
        "return_1d_pct": return_1d,
        "return_5d_pct": return_5d,
        "return_20d_pct": return_20d,
        "volatility_20d_pct": volatility_20d,
        "volume_ratio": volume_ratio,
        "recent_high": _round(recent_high),
        "recent_low": _round(recent_low),
        "distance_to_sma_20_pct": distance_to_sma_20_pct,
        "distance_to_sma_50_pct": distance_to_sma_50_pct,
        "rsi_14": rsi_14,
        "atr_14": atr_14,
        "atr_pct": atr_pct,
        "trend": trend,
    }


def build_historical_signal(
    ticker: str,
    candle: dict[str, Any],
    technical: dict[str, Any],
) -> dict[str, Any]:
    close = _to_float(candle.get("close"))
    sma_20 = _to_float(technical.get("sma_20"))
    sma_50 = _to_float(technical.get("sma_50"))
    return_5d = _to_float(technical.get("return_5d_pct"))
    return_20d = _to_float(technical.get("return_20d_pct"))
    volume_ratio = _to_float(technical.get("volume_ratio"))
    recent_high = _to_float(technical.get("recent_high"))
    recent_low = _to_float(technical.get("recent_low"))
    volatility = _to_float(technical.get("volatility_20d_pct"))

    if close is None or sma_20 is None or sma_50 is None:
        return {
            "ok": False,
            "action": "insufficient_data",
            "label": "Недостаточно данных",
        }

    reasons = []

    if close > sma_20:
        reasons.append("Цена выше SMA20.")
    else:
        reasons.append("Цена ниже SMA20.")

    if sma_20 > sma_50:
        reasons.append("SMA20 выше SMA50 — среднесрочная структура позитивная.")
    else:
        reasons.append("SMA20 ниже SMA50 — среднесрочная структура слабая.")

    if return_5d is not None:
        if return_5d > 1:
            reasons.append(f"Положительный импульс за 5 свечей: {return_5d}%.")
        elif return_5d < -1:
            reasons.append(f"Отрицательный импульс за 5 свечей: {return_5d}%.")
        else:
            reasons.append("Импульс за 5 свечей умеренный.")

    if volume_ratio is not None:
        if volume_ratio >= 1.2:
            reasons.append(f"Объём выше среднего: {volume_ratio}x.")
        elif volume_ratio <= 0.7:
            reasons.append(f"Объём ниже среднего: {volume_ratio}x.")
        else:
            reasons.append(f"Объём около среднего: {volume_ratio}x.")

    risk_level = "умеренный"
    if volatility is not None:
        if volatility >= 2.5:
            risk_level = "высокий"
        elif volatility <= 1:
            risk_level = "умеренный"
        else:
            risk_level = "средний"

    if close > sma_20 and sma_20 > sma_50 and (return_5d or 0) > 1:
        entry_price = recent_high or close
        stop_loss = recent_low or round(close * 0.96, 2)
        target_price = round(entry_price * 1.04, 2)

        confidence = 55

        if close > sma_20:
            confidence += 8
        if sma_20 > sma_50:
            confidence += 8
        if return_5d and return_5d > 2:
            confidence += 7
        if volume_ratio and volume_ratio >= 1:
            confidence += 5

        confidence = min(confidence, 85)

        return {
            "ok": True,
            "action": "buy_watch",
            "label": "Кандидат на покупку",
            "entry_price": _round(entry_price),
            "target_price": _round(target_price),
            "stop_loss": _round(stop_loss),
            "confidence_pct": float(confidence),
            "risk_level": risk_level,
            "horizon": "1–4 недели",
            "recent_high": _round(recent_high),
            "recent_low": _round(recent_low),
            "summary": "Исторический технический сценарий роста.",
            "reasons": reasons,
        }

    if close < sma_20 and sma_20 < sma_50 and ((return_5d or 0) < -1 or (return_20d or 0) < -3):
        target_price = recent_low or round(close * 0.96, 2)
        stop_loss = recent_high or round(close * 1.04, 2)

        confidence = 30

        if close < sma_20:
            confidence += 8
        if sma_20 < sma_50:
            confidence += 8
        if return_5d and return_5d < -2:
            confidence += 7
        if return_20d and return_20d < -5:
            confidence += 7

        confidence = min(confidence, 80)

        return {
            "ok": True,
            "action": "risk_sell_watch",
            "label": "Сигнал слабости / риск снижения",
            "entry_price": None,
            "target_price": _round(target_price),
            "stop_loss": _round(stop_loss),
            "confidence_pct": float(confidence),
            "risk_level": risk_level,
            "horizon": "1–3 недели",
            "recent_high": _round(recent_high),
            "recent_low": _round(recent_low),
            "summary": "Исторический сценарий риска снижения.",
            "reasons": reasons,
        }

    return {
        "ok": True,
        "action": "hold_watch",
        "label": "Нейтрально / наблюдать",
        "entry_price": None,
        "target_price": _round(recent_high),
        "stop_loss": _round(recent_low),
        "confidence_pct": 50.0,
        "risk_level": risk_level,
        "horizon": "1–3 недели",
        "recent_high": _round(recent_high),
        "recent_low": _round(recent_low),
        "summary": "Исторический нейтральный сигнал.",
        "reasons": reasons,
    }



def build_historical_signal_v2(
    history: list[dict[str, Any]],
    candle: dict[str, Any],
    technical: dict[str, Any],
) -> dict[str, Any]:
    close = _to_float(candle.get("close"))
    sma_20 = _to_float(technical.get("sma_20"))
    sma_50 = _to_float(technical.get("sma_50"))
    return_5d = _to_float(technical.get("return_5d_pct"))
    return_20d = _to_float(technical.get("return_20d_pct"))
    volume_ratio = _to_float(technical.get("volume_ratio"))
    recent_high = _to_float(technical.get("recent_high"))
    recent_low = _to_float(technical.get("recent_low"))
    volatility = _to_float(technical.get("volatility_20d_pct"))
    rsi_14 = _to_float(technical.get("rsi_14"))
    atr_14 = _to_float(technical.get("atr_14"))

    if close is None or sma_20 is None or sma_50 is None:
        return {
            "ok": False,
            "action": "insufficient_data",
            "label": "Недостаточно данных",
            "model_version": TECH_V2_MODEL_VERSION,
        }

    reasons: list[str] = []

    score = 50.0

    if close > sma_20:
        score += 8
        reasons.append("Цена выше SMA20.")
    else:
        score -= 8
        reasons.append("Цена ниже SMA20.")

    if sma_20 > sma_50:
        score += 8
        reasons.append("SMA20 выше SMA50 — структура позитивная.")
    else:
        score -= 8
        reasons.append("SMA20 ниже SMA50 — структура слабая.")

    if return_5d is not None:
        if return_5d >= 1.5:
            score += 7
            reasons.append(f"Импульс за 5 свечей положительный: {return_5d}%.")
        elif return_5d <= -1.5:
            score -= 7
            reasons.append(f"Импульс за 5 свечей отрицательный: {return_5d}%.")

    if return_20d is not None:
        if return_20d >= 4:
            score += 4
            reasons.append(f"20-свечной импульс положительный: {return_20d}%.")
        elif return_20d <= -4:
            score -= 4
            reasons.append(f"20-свечной импульс отрицательный: {return_20d}%.")

    if rsi_14 is not None:
        if 45 <= rsi_14 <= 68:
            score += 5
            reasons.append(f"RSI14 в рабочей зоне: {rsi_14}.")
        elif rsi_14 > 75:
            score -= 8
            reasons.append(f"RSI14 перегрет: {rsi_14}.")
        elif rsi_14 < 30:
            score -= 4
            reasons.append(f"RSI14 перепродан, но тренд требует подтверждения: {rsi_14}.")
        else:
            reasons.append(f"RSI14 нейтральный: {rsi_14}.")

    if volume_ratio is not None:
        if volume_ratio >= 1.2:
            score += 4
            reasons.append(f"Объём выше среднего: {volume_ratio}x.")
        elif volume_ratio <= 0.7:
            score -= 2
            reasons.append(f"Объём ниже среднего: {volume_ratio}x.")
        else:
            reasons.append(f"Объём около среднего: {volume_ratio}x.")

    risk_level = "умеренный"
    if volatility is not None:
        if volatility >= 2.5:
            risk_level = "высокий"
        elif volatility >= 1.2:
            risk_level = "средний"

    atr = atr_14 or (close * 0.02)

    # v2: покупка только если тренд + импульс + RSI не перегрет.
    if (
        close > sma_20
        and sma_20 > sma_50
        and (return_5d or 0) > 1
        and (rsi_14 is None or rsi_14 < 75)
    ):
        entry_price = max(recent_high or close, close)
        stop_loss = max(0.01, entry_price - atr * 2)
        target_price = entry_price + atr * 2.8

        confidence = max(55, min(85, score + 10))

        return {
            "ok": True,
            "model_version": TECH_V2_MODEL_VERSION,
            "action": "buy_watch",
            "label": "Кандидат на покупку v2",
            "entry_price": _round(entry_price),
            "target_price": _round(target_price),
            "stop_loss": _round(stop_loss),
            "confidence_pct": float(round(confidence, 0)),
            "risk_level": risk_level,
            "horizon": "1–4 недели",
            "recent_high": _round(recent_high),
            "recent_low": _round(recent_low),
            "summary": "tech_v2: сценарий роста с фильтром RSI и ATR-уровнями.",
            "reasons": reasons,
        }

    # v2: риск снижения, если тренд слабый и нет глубокой перепроданности.
    if (
        close < sma_20
        and sma_20 < sma_50
        and ((return_5d or 0) < -1 or (return_20d or 0) < -4)
        and (rsi_14 is None or rsi_14 > 25)
    ):
        target_price = max(0.01, close - atr * 2.2)
        stop_loss = close + atr * 2.0

        confidence = max(45, min(82, 100 - score + 10))

        return {
            "ok": True,
            "model_version": TECH_V2_MODEL_VERSION,
            "action": "risk_sell_watch",
            "label": "Риск снижения v2",
            "entry_price": None,
            "target_price": _round(target_price),
            "stop_loss": _round(stop_loss),
            "confidence_pct": float(round(confidence, 0)),
            "risk_level": risk_level,
            "horizon": "1–3 недели",
            "recent_high": _round(recent_high),
            "recent_low": _round(recent_low),
            "summary": "tech_v2: сценарий снижения с фильтром RSI и ATR-уровнями.",
            "reasons": reasons,
        }

    return {
        "ok": True,
        "model_version": TECH_V2_MODEL_VERSION,
        "action": "hold_watch",
        "label": "Нейтрально / наблюдать v2",
        "entry_price": None,
        "target_price": _round(recent_high),
        "stop_loss": _round(recent_low),
        "confidence_pct": 50.0,
        "risk_level": risk_level,
        "horizon": "1–3 недели",
        "recent_high": _round(recent_high),
        "recent_low": _round(recent_low),
        "summary": "tech_v2: нет достаточного преимущества для directional-сигнала.",
        "reasons": reasons,
    }



def _risk_reward_ratio(
    entry_price: Any,
    target_price: Any,
    stop_loss: Any,
) -> float | None:
    entry = _to_float(entry_price)
    target = _to_float(target_price)
    stop = _to_float(stop_loss)

    if entry is None or target is None or stop is None:
        return None

    reward = target - entry
    risk = entry - stop

    if reward <= 0 or risk <= 0:
        return None

    return round(reward / risk, 2)


def build_historical_signal_v4(
    history: list[dict[str, Any]],
    candle: dict[str, Any],
    technical: dict[str, Any],
) -> dict[str, Any]:
    """
    tech_v4:
    - направление и ATR-уровни берём из v3;
    - усиливаем quality-filter: risk/reward, RSI, объём и волатильность;
    - слабые buy-сценарии переводим в hold_watch, чтобы модель была строже.
    """
    base = build_historical_signal_v3(history, candle, technical)

    if not base or base.get("ok") is False:
        result = dict(base or {})
        result["model_version"] = TECH_V4_MODEL_VERSION
        return result

    action = base.get("action")
    reasons = list(base.get("reasons") or [])
    rsi_14 = _to_float(technical.get("rsi_14"))
    volume_ratio = _to_float(technical.get("volume_ratio"))
    volatility = _to_float(technical.get("volatility_20d_pct"))
    return_20d = _to_float(technical.get("return_20d_pct"))

    rr = _risk_reward_ratio(
        base.get("entry_price"),
        base.get("target_price"),
        base.get("stop_loss"),
    )

    quality_score = 50.0

    if rr is not None:
        if rr >= 1.8:
            quality_score += 18
            reasons.append(f"tech_v4: сильный risk/reward ≈ {rr}.")
        elif rr >= 1.3:
            quality_score += 10
            reasons.append(f"tech_v4: приемлемый risk/reward ≈ {rr}.")
        else:
            quality_score -= 15
            reasons.append(f"tech_v4: слабый risk/reward ≈ {rr}.")
    else:
        quality_score -= 10
        reasons.append("tech_v4: risk/reward не удалось рассчитать.")

    if rsi_14 is not None:
        if 45 <= rsi_14 <= 68:
            quality_score += 8
            reasons.append("tech_v4: RSI в рабочей зоне.")
        elif rsi_14 >= 76:
            quality_score -= 18
            reasons.append("tech_v4: RSI перегрет, риск позднего входа.")
        elif rsi_14 <= 35:
            quality_score -= 8
            reasons.append("tech_v4: RSI слабый, нужен разворот/подтверждение.")

    if volume_ratio is not None:
        if volume_ratio >= 1.0:
            quality_score += 5
            reasons.append("tech_v4: объём подтверждает движение.")
        elif volume_ratio < 0.55:
            quality_score -= 8
            reasons.append("tech_v4: объём слишком низкий для качественного сигнала.")

    if volatility is not None:
        if volatility <= 1.8:
            quality_score += 4
        elif volatility >= 3.0:
            quality_score -= 10
            reasons.append("tech_v4: волатильность повышена, риск выбивания стопа.")

    if return_20d is not None and return_20d < -4:
        quality_score -= 8
        reasons.append("tech_v4: 20-свечной фон слабый.")

    quality_score = round(max(0.0, min(100.0, quality_score)), 0)

    if action in {"buy_watch", "watch_buy"}:
        block_reasons: list[str] = []

        if rr is None or rr < 1.2:
            block_reasons.append("risk/reward ниже 1.2")
        if rsi_14 is not None and rsi_14 >= 76:
            block_reasons.append("RSI перегрет")
        if volume_ratio is not None and volume_ratio < 0.55:
            block_reasons.append("объём слабый")
        if volatility is not None and volatility >= 3.0:
            block_reasons.append("волатильность высокая")

        if block_reasons:
            reasons.append("tech_v4: buy переведён в наблюдение: " + ", ".join(block_reasons) + ".")
            return {
                **base,
                "model_version": TECH_V4_MODEL_VERSION,
                "action": "hold_watch",
                "label": "Нейтрально / quality-фильтр v4",
                "entry_price": None,
                "confidence_pct": min(_to_float(base.get("confidence_pct")) or 50.0, 55.0),
                "quality_score": quality_score,
                "risk_reward_ratio": rr,
                "summary": "tech_v4: directional buy-сигнал заблокирован quality-фильтром.",
                "reasons": reasons,
            }

        confidence = _to_float(base.get("confidence_pct")) or 60.0
        confidence = round(max(confidence, min(92.0, confidence + quality_score * 0.08)), 0)

        return {
            **base,
            "model_version": TECH_V4_MODEL_VERSION,
            "label": "Кандидат на покупку v4 quality",
            "confidence_pct": confidence,
            "quality_score": quality_score,
            "risk_reward_ratio": rr,
            "summary": "tech_v4: качественный buy-сценарий с risk/reward-фильтром.",
            "reasons": reasons,
        }

    return {
        **base,
        "model_version": TECH_V4_MODEL_VERSION,
        "quality_score": quality_score,
        "risk_reward_ratio": rr,
        "label": (base.get("label") or "Сигнал") + " v4",
        "summary": "tech_v4: quality-score рассчитан, directional buy-фильтр применён.",
        "reasons": reasons,
    }

def build_historical_signal_v3(
    history: list[dict[str, Any]],
    candle: dict[str, Any],
    technical: dict[str, Any],
) -> dict[str, Any]:
    """
    tech_v3:
    - направление берём из устойчивой v1-логики;
    - target/stop считаем через ATR, чтобы уровни зависели от волатильности;
    - стоп для buy шире, чем в v2, чтобы не выбивало рыночным шумом.
    """
    base = build_historical_signal(history, candle, technical)

    if not base or base.get("ok") is False:
        result = dict(base or {})
        result["model_version"] = TECH_V3_MODEL_VERSION
        return result

    close = _to_float(candle.get("close"))
    recent_high = _to_float(technical.get("recent_high"))
    recent_low = _to_float(technical.get("recent_low"))
    atr_14 = _to_float(technical.get("atr_14"))
    rsi_14 = _to_float(technical.get("rsi_14"))
    volatility = _to_float(technical.get("volatility_20d_pct"))

    if close is None:
        result = dict(base)
        result["model_version"] = TECH_V3_MODEL_VERSION
        return result

    atr = atr_14 or max(close * 0.018, 0.01)

    risk_level = base.get("risk_level") or "умеренный"
    if volatility is not None:
        if volatility >= 2.5:
            risk_level = "высокий"
        elif volatility >= 1.2:
            risk_level = "средний"
        else:
            risk_level = "умеренный"

    action = base.get("action")
    reasons = list(base.get("reasons") or [])
    reasons.append(f"tech_v3: уровни рассчитаны через ATR14 ≈ {round(atr, 2)}.")

    if rsi_14 is not None:
        reasons.append(f"RSI14: {rsi_14}.")

    # Покупка: направление v1, но цель/стоп через ATR.
    if action in {"buy_watch", "watch_buy"}:
        # Если RSI слишком перегрет, не даём buy, переводим в наблюдение.
        if rsi_14 is not None and rsi_14 >= 78:
            return {
                **base,
                "model_version": TECH_V3_MODEL_VERSION,
                "action": "hold_watch",
                "label": "Нейтрально / перегрев v3",
                "entry_price": None,
                "target_price": _round(recent_high),
                "stop_loss": _round(recent_low),
                "confidence_pct": 50.0,
                "risk_level": risk_level,
                "summary": "tech_v3: buy-сигнал заблокирован из-за перегрева RSI.",
                "reasons": reasons,
            }

        entry_price = max(recent_high or close, close)

        atr_stop = entry_price - atr * 2.6
        range_stop = recent_low if recent_low is not None and recent_low < entry_price else atr_stop
        stop_loss = min(atr_stop, range_stop)

        target_by_atr = entry_price + atr * 3.0
        target_by_pct = entry_price * 1.035
        target_price = max(target_by_atr, target_by_pct)

        confidence = _to_float(base.get("confidence_pct")) or 60.0
        confidence = min(88.0, confidence + 3.0)

        return {
            **base,
            "model_version": TECH_V3_MODEL_VERSION,
            "action": "buy_watch",
            "label": "Кандидат на покупку v3",
            "entry_price": _round(entry_price),
            "target_price": _round(target_price),
            "stop_loss": _round(stop_loss),
            "confidence_pct": _round(confidence, 0),
            "risk_level": risk_level,
            "summary": "tech_v3: сценарий роста с ATR-целью и расширенным ATR-стопом.",
            "reasons": reasons,
        }

    # Риск снижения: направление v1, но уровни через ATR.
    if action == "risk_sell_watch":
        target_by_atr = close - atr * 2.0
        if recent_low is not None and recent_low < close:
            target_price = min(recent_low, target_by_atr)
        else:
            target_price = target_by_atr

        stop_loss = close + atr * 2.4

        confidence = _to_float(base.get("confidence_pct")) or 50.0
        confidence = min(86.0, confidence + 4.0)

        return {
            **base,
            "model_version": TECH_V3_MODEL_VERSION,
            "action": "risk_sell_watch",
            "label": "Риск снижения v3",
            "entry_price": None,
            "target_price": _round(max(target_price, 0.01)),
            "stop_loss": _round(stop_loss),
            "confidence_pct": _round(confidence, 0),
            "risk_level": risk_level,
            "summary": "tech_v3: сценарий снижения с ATR-целью и ATR-стопом.",
            "reasons": reasons,
        }

    # Нейтральный сигнал: оставляем neutral, но явно маркируем v3.
    return {
        **base,
        "model_version": TECH_V3_MODEL_VERSION,
        "label": "Нейтрально / наблюдать v3",
        "risk_level": risk_level,
        "summary": "tech_v3: нет достаточного преимущества для directional-сигнала.",
        "reasons": reasons,
    }

def _evaluate_signal(
    signal_row: dict[str, Any],
    future_candles: list[dict[str, Any]],
) -> dict[str, Any]:
    action = signal_row.get("action")

    if action in {"buy_watch", "watch_buy"}:
        return evaluate_buy_signal(signal_row, future_candles)

    if action == "risk_sell_watch":
        return evaluate_risk_signal(signal_row, future_candles)

    return evaluate_neutral_signal(signal_row, future_candles)


def _strategy_result_pct(row: dict[str, Any]) -> float | None:
    evaluation = row.get("evaluation") or {}
    status = evaluation.get("status")
    action = row.get("action")
    raw_result = _to_float(evaluation.get("result_pct"))

    if raw_result is None:
        return None

    if status not in {"success", "failed"}:
        return None

    if action in {"buy_watch", "watch_buy"}:
        return round(raw_result, 2)

    if action == "risk_sell_watch":
        return round(-raw_result, 2)

    return None


def _build_backtest_stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
    success = sum(1 for row in rows if (row.get("evaluation") or {}).get("status") == "success")
    failed = sum(1 for row in rows if (row.get("evaluation") or {}).get("status") == "failed")
    ambiguous = sum(1 for row in rows if (row.get("evaluation") or {}).get("status") == "ambiguous")
    open_count = sum(1 for row in rows if (row.get("evaluation") or {}).get("status") == "open")
    pending = sum(1 for row in rows if (row.get("evaluation") or {}).get("status") == "pending")
    not_triggered = sum(1 for row in rows if (row.get("evaluation") or {}).get("status") == "not_triggered")
    neutral = sum(1 for row in rows if (row.get("evaluation") or {}).get("status") == "neutral")

    accuracy_pct = None
    if success + failed > 0:
        accuracy_pct = round(success / (success + failed) * 100, 2)

    raw_values = [
        _to_float((row.get("evaluation") or {}).get("result_pct"))
        for row in rows
        if _to_float((row.get("evaluation") or {}).get("result_pct")) is not None
    ]

    strategy_values = [
        _to_float(row.get("strategy_result_pct"))
        for row in rows
        if _to_float(row.get("strategy_result_pct")) is not None
    ]

    avg_result_pct = round(sum(raw_values) / len(raw_values), 2) if raw_values else None
    avg_strategy_result_pct = round(sum(strategy_values) / len(strategy_values), 2) if strategy_values else None

    return {
        "total": len(rows),
        "success": success,
        "failed": failed,
        "ambiguous": ambiguous,
        "open": open_count,
        "pending": pending,
        "not_triggered": not_triggered,
        "neutral": neutral,
        "accuracy_pct": accuracy_pct,
        "avg_result_pct": avg_result_pct,
        "avg_strategy_result_pct": avg_strategy_result_pct,
        "actionable_count": success + failed,
        "buy_watch": sum(1 for row in rows if row.get("action") == "buy_watch"),
        "watch_buy": sum(1 for row in rows if row.get("action") == "watch_buy"),
        "hold_watch": sum(1 for row in rows if row.get("action") == "hold_watch"),
        "risk_sell_watch": sum(1 for row in rows if row.get("action") == "risk_sell_watch"),
    }


def _build_group_stats(
    rows: list[dict[str, Any]],
    key: str,
    output_key: str,
) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = {}

    for row in rows:
        value = str(row.get(key) or "—")
        groups.setdefault(value, []).append(row)

    result = []
    for value, group_rows in groups.items():
        result.append({
            output_key: value,
            **_build_backtest_stats(group_rows),
        })

    return sorted(
        result,
        key=lambda item: (
            item.get("actionable_count") or 0,
            item.get("total") or 0,
            str(item.get(output_key) or ""),
        ),
        reverse=True,
    )


def _quote_sql_name(name: str) -> str:
    return '"' + str(name).replace('"', '""') + '"'


def _find_candle_table(db: Any) -> dict[str, str]:
    from sqlalchemy import text as sql_text

    tables = db.execute(
        sql_text("SELECT name FROM sqlite_master WHERE type='table'")
    ).scalars().all()

    required_any = {
        "ticker": ["ticker", "secid", "symbol"],
        "trade_date": ["trade_date", "date", "tradedate"],
        "open": ["open"],
        "high": ["high"],
        "low": ["low"],
        "close": ["close", "last"],
    }

    optional_any = {
        "volume": ["volume", "vol"],
        "value_rub": ["value_rub", "value", "turnover", "val"],
        "board": ["board", "boardid"],
    }

    for table in tables:
        cols_rows = db.execute(sql_text(f"PRAGMA table_info({_quote_sql_name(table)})")).all()
        cols = [row[1] for row in cols_rows]
        cols_lower = {c.lower(): c for c in cols}

        mapping: dict[str, str] = {}

        ok = True
        for out_key, variants in required_any.items():
            found = None
            for variant in variants:
                if variant.lower() in cols_lower:
                    found = cols_lower[variant.lower()]
                    break
            if not found:
                ok = False
                break
            mapping[out_key] = found

        if not ok:
            continue

        for out_key, variants in optional_any.items():
            for variant in variants:
                if variant.lower() in cols_lower:
                    mapping[out_key] = cols_lower[variant.lower()]
                    break

        mapping["table"] = table
        return mapping

    raise RuntimeError("Не найдена таблица свечей с колонками ticker/date/open/high/low/close.")


def _ticker_candles(
    db: Any,
    ticker: str,
    fetch_limit: int = 180,
) -> list[dict[str, Any]]:
    from sqlalchemy import text as sql_text

    mapping = _find_candle_table(db)

    table = _quote_sql_name(mapping["table"])
    ticker_col = _quote_sql_name(mapping["ticker"])
    date_col = _quote_sql_name(mapping["trade_date"])

    select_parts = [
        f"{_quote_sql_name(mapping['ticker'])} AS ticker",
        f"{_quote_sql_name(mapping['trade_date'])} AS trade_date",
        f"{_quote_sql_name(mapping['open'])} AS open",
        f"{_quote_sql_name(mapping['high'])} AS high",
        f"{_quote_sql_name(mapping['low'])} AS low",
        f"{_quote_sql_name(mapping['close'])} AS close",
    ]

    if "board" in mapping:
        select_parts.append(f"{_quote_sql_name(mapping['board'])} AS board")
    else:
        select_parts.append("'TQBR' AS board")

    if "volume" in mapping:
        select_parts.append(f"{_quote_sql_name(mapping['volume'])} AS volume")
    else:
        select_parts.append("NULL AS volume")

    if "value_rub" in mapping:
        select_parts.append(f"{_quote_sql_name(mapping['value_rub'])} AS value_rub")
    else:
        select_parts.append("NULL AS value_rub")

    sql = f"""
        SELECT {", ".join(select_parts)}
        FROM {table}
        WHERE UPPER({ticker_col}) = UPPER(:ticker)
        ORDER BY {date_col} DESC
        LIMIT :limit
    """

    rows = db.execute(
        sql_text(sql),
        {"ticker": ticker, "limit": int(fetch_limit)},
    ).mappings().all()

    candles = []
    for row in reversed(rows):
        candles.append({
            "ticker": str(row.get("ticker") or ticker).upper(),
            "board": row.get("board") or "TQBR",
            "trade_date": str(row.get("trade_date")),
            "open": _to_float(row.get("open")),
            "high": _to_float(row.get("high")),
            "low": _to_float(row.get("low")),
            "close": _to_float(row.get("close")),
            "volume": _to_float(row.get("volume")),
            "value_rub": _to_float(row.get("value_rub")),
        })

    return candles


def _call_historical_signal(
    history: list[dict[str, Any]],
    technical: dict[str, Any],
    model_version: str = SIGNAL_MODEL_VERSION,
) -> dict[str, Any]:
    candle = history[-1] if history else {}

    if model_version == TECH_V2_MODEL_VERSION:
        return build_historical_signal_v2(history, candle, technical)

    if model_version == TECH_V3_MODEL_VERSION:
        return build_historical_signal_v3(history, candle, technical)

    if model_version == TECH_V4_MODEL_VERSION:
        return build_historical_signal_v4(history, candle, technical)

    return build_historical_signal(history, candle, technical)


def run_signals_backtest(
    db: Any,
    tickers: str | list[str] = "SBER,GAZP,LKOH,PLZL",
    limit: int = 150,
    min_history: int = 60,
    future_limit: int = 20,
    max_points_per_ticker: int = 25,
    action: str | None = None,
    model_version: str = SIGNAL_MODEL_VERSION,
) -> dict[str, Any]:
    if isinstance(tickers, str):
        ticker_list = [
            item.strip().upper()
            for item in tickers.split(",")
            if item.strip()
        ]
    else:
        ticker_list = [
            str(item).strip().upper()
            for item in tickers
            if str(item).strip()
        ]

    if model_version not in AVAILABLE_SIGNAL_MODEL_VERSIONS:
        model_version = SIGNAL_MODEL_VERSION

    rows: list[dict[str, Any]] = []

    fetch_limit = max(
        int(min_history) + int(future_limit) + int(max_points_per_ticker) + 20,
        120,
    )

    for ticker in ticker_list:
        candles = _ticker_candles(
            db=db,
            ticker=ticker,
            fetch_limit=fetch_limit,
        )

        if len(candles) < min_history + future_limit:
            continue

        last_signal_index = len(candles) - int(future_limit) - 1
        indices = list(range(int(min_history) - 1, last_signal_index + 1))
        indices = indices[-int(max_points_per_ticker):]

        for index in indices:
            history = candles[: index + 1]
            future = candles[index + 1 : index + 1 + int(future_limit)]
            current = history[-1]

            technical = build_historical_technical(history)
            signal = _call_historical_signal(history, technical, model_version=model_version)

            if not signal or signal.get("ok") is False:
                continue

            signal_action = signal.get("action")
            if action and signal_action != action:
                continue

            close = _to_float(current.get("close"))
            previous_close = _to_float(history[-2].get("close")) if len(history) >= 2 else None

            row = {
                "id": f"{ticker}-{current.get('trade_date')}",
                "created_at": current.get("trade_date"),
                "ticker": ticker,
                "trade_date": current.get("trade_date"),
                "price": close,
                "change_pct": _pct_change(close, previous_close),
                "action": signal_action,
                "label": signal.get("label"),
                "entry_price": _to_float(signal.get("entry_price")),
                "target_price": _to_float(signal.get("target_price")),
                "stop_loss": _to_float(signal.get("stop_loss")),
                "confidence_pct": _to_float(signal.get("confidence_pct")),
                "risk_level": signal.get("risk_level"),
                "horizon": signal.get("horizon"),
                "reasons": signal.get("reasons") or [],
                "technical": technical,
                "signal": signal,
                "model_version": signal.get("model_version") or model_version,
                "ticker_url": f"/tickers/{ticker}",
                "future_candles_count": len(future),
            }

            row["evaluation"] = _evaluate_signal(row, future)
            row["strategy_result_pct"] = _strategy_result_pct(row)

            rows.append(row)

    rows = sorted(
        rows,
        key=lambda row: str(row.get("trade_date") or ""),
        reverse=True,
    )[: int(limit)]

    summary = _build_backtest_stats(rows)
    by_action = _build_group_stats(rows, key="action", output_key="action")
    by_ticker = _build_group_stats(rows, key="ticker", output_key="ticker")

    return {
        "params": {
            "tickers": ticker_list,
            "limit": limit,
            "min_history": min_history,
            "future_limit": future_limit,
            "max_points_per_ticker": max_points_per_ticker,
            "action": action,
            "model_version": model_version,
        },
        "summary": summary,
        "by_action": by_action,
        "by_ticker": by_ticker,
        "rows": rows,
    }

