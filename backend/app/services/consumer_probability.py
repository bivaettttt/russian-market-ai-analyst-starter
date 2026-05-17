from __future__ import annotations

from dataclasses import dataclass
from statistics import mean, pstdev
from typing import Any


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


def _clean_floats(values: list[Any]) -> list[float]:
    result: list[float] = []
    for value in values:
        number = _to_float(value)
        if number is not None:
            result.append(number)
    return result


def _avg(values: list[Any]) -> float | None:
    clean = _clean_floats(values)
    if not clean:
        return None
    return sum(clean) / len(clean)


def _ema(values: list[float], period: int) -> float | None:
    if len(values) < period:
        return None
    alpha = 2 / (period + 1)
    ema_value = sum(values[:period]) / period
    for value in values[period:]:
        ema_value = alpha * value + (1 - alpha) * ema_value
    return ema_value


def _rsi(values: list[float], period: int = 14) -> float | None:
    if len(values) < period + 1:
        return None

    gains: list[float] = []
    losses: list[float] = []

    for prev, current in zip(values[-period - 1:-1], values[-period:]):
        diff = current - prev
        if diff >= 0:
            gains.append(diff)
            losses.append(0.0)
        else:
            gains.append(0.0)
            losses.append(abs(diff))

    avg_gain = mean(gains) if gains else 0.0
    avg_loss = mean(losses) if losses else 0.0

    if avg_loss == 0:
        return 100.0

    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def _atr(candles: list[dict[str, Any]], period: int = 14) -> float | None:
    if len(candles) < period + 1:
        return None

    true_ranges: list[float] = []
    tail = candles[-period - 1:]

    for previous, current in zip(tail[:-1], tail[1:]):
        high = _to_float(current.get("high"))
        low = _to_float(current.get("low"))
        prev_close = _to_float(previous.get("close"))

        if high is None or low is None or prev_close is None:
            continue

        true_ranges.append(max(high - low, abs(high - prev_close), abs(low - prev_close)))

    if not true_ranges:
        return None

    return mean(true_ranges)


@dataclass
class HistoricalCalibration:
    samples: int
    success: int
    failed: int
    hit_rate_pct: float | None
    target_pct: float | None
    stop_pct: float | None
    horizon_days: int


def _historical_tp_before_sl_calibration(
    candles: list[dict[str, Any]],
    action: str | None,
    price: float | None,
    target_price: float | None,
    stop_loss: float | None,
    horizon_days: int = 20,
    max_samples: int = 220,
) -> HistoricalCalibration:
    if price in (None, 0) or target_price is None or len(candles) < horizon_days + 35:
        return HistoricalCalibration(0, 0, 0, None, None, None, horizon_days)

    is_downside = action == "risk_sell_watch" or target_price < price

    if is_downside:
        target_pct = abs(_pct_change(target_price, price) or 0)
        if stop_loss is not None and stop_loss > price:
            stop_pct = abs(_pct_change(stop_loss, price) or 0)
        else:
            stop_pct = max(target_pct / 2, 2.0)
    else:
        target_pct = _pct_change(target_price, price) or 0
        if stop_loss is not None and stop_loss < price:
            stop_pct = abs(_pct_change(stop_loss, price) or 0)
        else:
            stop_pct = max(target_pct / 2, 2.0)

    target_pct = abs(target_pct)
    stop_pct = abs(stop_pct)

    if target_pct <= 0 or stop_pct <= 0:
        return HistoricalCalibration(0, 0, 0, None, target_pct, stop_pct, horizon_days)

    usable = candles[-max_samples - horizon_days - 1:]
    success = 0
    failed = 0

    for index in range(0, len(usable) - horizon_days - 1):
        entry = _to_float(usable[index].get("close"))
        if entry in (None, 0):
            continue

        if is_downside:
            target_level = entry * (1 - target_pct / 100)
            stop_level = entry * (1 + stop_pct / 100)
        else:
            target_level = entry * (1 + target_pct / 100)
            stop_level = entry * (1 - stop_pct / 100)

        outcome: bool | None = None

        for future in usable[index + 1:index + horizon_days + 1]:
            high = _to_float(future.get("high"))
            low = _to_float(future.get("low"))
            if high is None or low is None:
                continue

            if is_downside:
                hit_target = low <= target_level
                hit_stop = high >= stop_level
            else:
                hit_target = high >= target_level
                hit_stop = low <= stop_level

            # Если TP и SL в одной дневной свече, порядок неизвестен. Считаем консервативно как неуспех.
            if hit_target and hit_stop:
                outcome = False
                break
            if hit_stop:
                outcome = False
                break
            if hit_target:
                outcome = True
                break

        if outcome is True:
            success += 1
        elif outcome is False:
            failed += 1

    samples = success + failed
    hit_rate = round(success / samples * 100, 1) if samples else None

    return HistoricalCalibration(
        samples=samples,
        success=success,
        failed=failed,
        hit_rate_pct=hit_rate,
        target_pct=round(target_pct, 2),
        stop_pct=round(stop_pct, 2),
        horizon_days=horizon_days,
    )


def _liquidity_stats(candles: list[dict[str, Any]]) -> dict[str, Any]:
    values = _clean_floats([row.get("value_rub") or row.get("value") for row in candles[-20:]])
    volumes = _clean_floats([row.get("volume") for row in candles[-20:]])

    avg_value = mean(values) if values else None
    avg_volume = mean(volumes) if volumes else None

    if avg_value is None:
        bucket = "unknown"
    elif avg_value >= 80_000_000:
        bucket = "high"
    elif avg_value >= 15_000_000:
        bucket = "medium"
    else:
        bucket = "low"

    return {
        "avg_value_20d_rub": _round(avg_value, 0),
        "avg_volume_20d": _round(avg_volume, 0),
        "liquidity_bucket": bucket,
    }


def _reliability_level(
    candles_count: int,
    calibration: HistoricalCalibration,
    liquidity_bucket: str,
    rr: float | None,
) -> tuple[str, int, list[str]]:
    score = 50
    reasons: list[str] = []

    if candles_count >= 180:
        score += 16
        reasons.append("достаточно истории для проверки сценария")
    elif candles_count >= 90:
        score += 6
        reasons.append("истории достаточно для базовой оценки")
    else:
        score -= 18
        reasons.append("истории мало, прогноз менее надёжен")

    if calibration.samples >= 40:
        score += 18
        reasons.append("есть репрезентативная историческая проверка похожей цели")
    elif calibration.samples >= 12:
        score += 8
        reasons.append("есть ограниченная историческая проверка")
    else:
        score -= 12
        reasons.append("мало похожих исторических срабатываний TP/SL")

    if liquidity_bucket == "high":
        score += 12
        reasons.append("ликвидность высокая")
    elif liquidity_bucket == "medium":
        score += 4
        reasons.append("ликвидность средняя")
    elif liquidity_bucket == "low":
        score -= 14
        reasons.append("ликвидность низкая, риск проскальзывания выше")

    if rr is not None:
        if rr >= 1.5:
            score += 8
            reasons.append("risk/reward приемлемый")
        elif rr < 1.0:
            score -= 10
            reasons.append("risk/reward слабый")

    score = int(_clamp(score, 0, 100))

    if score >= 72:
        level = "Высокая"
    elif score >= 48:
        level = "Средняя"
    else:
        level = "Низкая"

    return level, score, reasons


def build_probability_assessment(
    *,
    base_probability_pct: float | None,
    candles: list[dict[str, Any]],
    signal: dict[str, Any],
    technical: dict[str, Any],
    price: float | None,
    target_price: float | None,
    stop_loss: float | None,
    events: list[dict[str, Any]],
    horizon_days: int = 20,
) -> dict[str, Any]:
    base_probability = float(base_probability_pct if base_probability_pct is not None else 50.0)
    action = signal.get("action")
    rr = _to_float(signal.get("risk_reward_ratio"))
    liquidity = _liquidity_stats(candles)

    calibration = _historical_tp_before_sl_calibration(
        candles=candles,
        action=action,
        price=price,
        target_price=target_price,
        stop_loss=stop_loss,
        horizon_days=horizon_days,
    )

    probability = base_probability
    calibration_weight = 0.0

    if calibration.hit_rate_pct is not None:
        if calibration.samples >= 40:
            calibration_weight = 0.45
        elif calibration.samples >= 20:
            calibration_weight = 0.32
        elif calibration.samples >= 8:
            calibration_weight = 0.18

        probability = probability * (1 - calibration_weight) + calibration.hit_rate_pct * calibration_weight

    # Надёжностные штрафы, которые пользователь видит не как метрики, а как честное снижение вероятности.
    candles_count = len(candles)
    if candles_count < 60:
        probability -= 10
    elif candles_count < 120:
        probability -= 4

    if liquidity.get("liquidity_bucket") == "low":
        probability -= 7
    elif liquidity.get("liquidity_bucket") == "unknown":
        probability -= 3

    volatility = _to_float(technical.get("volatility_20d_pct"))
    if volatility is not None and volatility >= 3.2:
        probability -= 5

    for event in events:
        impact = str(event.get("impact") or "").lower()
        importance = _to_float(event.get("importance")) or 1
        weight = min(max(importance, 1), 5) * 0.7
        if "negative" in impact or "негат" in impact:
            probability -= weight
        elif "positive" in impact or "позит" in impact:
            probability += weight

    if action == "risk_sell_watch":
        probability = _clamp(probability, 12, 88)
    else:
        probability = _clamp(probability, 8, 92)

    reliability_level, reliability_score, reliability_reasons = _reliability_level(
        candles_count=candles_count,
        calibration=calibration,
        liquidity_bucket=str(liquidity.get("liquidity_bucket") or "unknown"),
        rr=rr,
    )

    return {
        "probability_pct": round(probability, 0),
        "base_probability_pct": round(base_probability, 0),
        "reliability_level": reliability_level,
        "reliability_score": reliability_score,
        "reliability_reasons": reliability_reasons,
        "calibration": {
            "method": "TP-before-SL historical calibration",
            "samples": calibration.samples,
            "success": calibration.success,
            "failed": calibration.failed,
            "hit_rate_pct": calibration.hit_rate_pct,
            "target_pct": calibration.target_pct,
            "stop_pct": calibration.stop_pct,
            "horizon_days": calibration.horizon_days,
            "weight_in_final_probability": round(calibration_weight, 2),
        },
        "liquidity": liquidity,
        "notes": [
            "Вероятность скорректирована исторической проверкой TP-before-SL, ликвидностью, глубиной истории и событиями.",
            "При малом числе исторических срабатываний система автоматически снижает надёжность прогноза.",
        ],
    }
