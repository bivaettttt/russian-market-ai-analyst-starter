from __future__ import annotations

import math
from statistics import mean, pstdev
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Candle, Instrument


FEATURE_SET_VERSION = "v2_extended_technical"

FEATURE_NAMES = [
    "ret_1",
    "ret_5",
    "ret_10",
    "ret_20",
    "ma_5_gap_pct",
    "ma_20_gap_pct",
    "ma_50_gap_pct",
    "volatility_20_pct",
    "atr_20_pct",
    "volume_ratio_20",
    "value_ratio_20",
    "dist_high_20_pct",
    "dist_low_20_pct",
    "range_today_pct",
    "positive_share_5_pct",
    "positive_share_10_pct",
    "positive_share_20_pct",
    "trend_stack_score",
    "momentum_accel_5_20",
    "range_position_20_pct",
    "range_position_60_pct",
    "dist_high_60_pct",
    "dist_low_60_pct",
    "volume_ratio_5_20",
    "value_ratio_5_20",
    "volume_cv_20_pct",
    "value_cv_20_pct",
    "liquidity_log_value_20",
]


def _safe_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        result = float(value)
        if math.isnan(result) or math.isinf(result):
            return None
        return result
    except (TypeError, ValueError):
        return None


def _pct_change(current: float | None, previous: float | None) -> float | None:
    if current is None or previous is None or previous == 0:
        return None
    return (current / previous - 1.0) * 100.0


def _avg(values: list[float | None]) -> float | None:
    clean = [float(value) for value in values if value is not None]
    if not clean:
        return None
    return mean(clean)


def _std(values: list[float | None]) -> float | None:
    clean = [float(value) for value in values if value is not None]
    if len(clean) < 2:
        return None
    return pstdev(clean)


def _cv_pct(values: list[float | None]) -> float | None:
    avg = _avg(values)
    std = _std(values)

    if avg is None or avg == 0 or std is None:
        return None

    return std / avg * 100.0


def _ratio(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator is None or denominator == 0:
        return None
    return numerator / denominator


def _range_position_pct(close: float | None, low: float | None, high: float | None) -> float | None:
    if close is None or low is None or high is None or high == low:
        return None
    return (close - low) / (high - low) * 100.0


def _positive_share_pct(returns: list[float | None]) -> float | None:
    clean = [value for value in returns if value is not None]
    if not clean:
        return None
    return sum(1 for value in clean if value > 0) / len(clean) * 100.0


def _returns_window(candles: list[Candle], start: int, end: int) -> list[float | None]:
    values: list[float | None] = []

    for index in range(start, end + 1):
        if index <= 0:
            continue

        current = _safe_float(candles[index].close)
        previous = _safe_float(candles[index - 1].close)
        values.append(_pct_change(current, previous))

    return values


def _feature_row(candles: list[Candle], index: int) -> list[float] | None:
    current = candles[index]
    close = _safe_float(current.close)
    high = _safe_float(current.high)
    low = _safe_float(current.low)
    volume = _safe_float(current.volume)
    value = _safe_float(current.value)

    if close is None or close <= 0:
        return None

    closes = [_safe_float(item.close) for item in candles[: index + 1]]
    highs = [_safe_float(item.high) for item in candles[: index + 1]]
    lows = [_safe_float(item.low) for item in candles[: index + 1]]
    volumes = [_safe_float(item.volume) for item in candles[: index + 1]]
    values = [_safe_float(item.value) for item in candles[: index + 1]]

    if len(closes) < 60 or any(item is None for item in closes[-60:]):
        return None

    def close_back(days: int) -> float | None:
        if index - days < 0:
            return None
        return _safe_float(candles[index - days].close)

    ret_1 = _pct_change(close, close_back(1))
    ret_5 = _pct_change(close, close_back(5))
    ret_10 = _pct_change(close, close_back(10))
    ret_20 = _pct_change(close, close_back(20))

    ma_5 = _avg(closes[-5:])
    ma_20 = _avg(closes[-20:])
    ma_50 = _avg(closes[-50:])

    ma_5_gap = _pct_change(close, ma_5)
    ma_20_gap = _pct_change(close, ma_20)
    ma_50_gap = _pct_change(close, ma_50)

    returns_5 = _returns_window(candles, index - 4, index)
    returns_10 = _returns_window(candles, index - 9, index)
    returns_20 = _returns_window(candles, index - 19, index)

    volatility_20 = _std(returns_20)

    ranges_20: list[float] = []
    for item in candles[max(0, index - 19): index + 1]:
        item_high = _safe_float(item.high)
        item_low = _safe_float(item.low)
        item_close = _safe_float(item.close)

        if item_high is not None and item_low is not None and item_close and item_close > 0:
            ranges_20.append((item_high - item_low) / item_close * 100.0)

    atr_20 = _avg(ranges_20)

    avg_volume_5 = _avg(volumes[-5:])
    avg_volume_20 = _avg(volumes[-20:])
    avg_value_5 = _avg(values[-5:])
    avg_value_20 = _avg(values[-20:])

    volume_ratio = _ratio(volume, avg_volume_20)
    value_ratio = _ratio(value, avg_value_20)

    high_20_values = [item for item in highs[-20:] if item is not None]
    low_20_values = [item for item in lows[-20:] if item is not None]
    high_60_values = [item for item in highs[-60:] if item is not None]
    low_60_values = [item for item in lows[-60:] if item is not None]

    high_20 = max(high_20_values) if high_20_values else None
    low_20 = min(low_20_values) if low_20_values else None
    high_60 = max(high_60_values) if high_60_values else None
    low_60 = min(low_60_values) if low_60_values else None

    dist_high_20 = _pct_change(high_20, close)
    dist_low_20 = _pct_change(close, low_20)
    dist_high_60 = _pct_change(high_60, close)
    dist_low_60 = _pct_change(close, low_60)

    range_today = None
    if high is not None and low is not None and close > 0:
        range_today = (high - low) / close * 100.0

    positive_share_5 = _positive_share_pct(returns_5)
    positive_share_10 = _positive_share_pct(returns_10)
    positive_share_20 = _positive_share_pct(returns_20)

    trend_stack_score = 0.0
    if ma_5 is not None and ma_20 is not None and ma_5 > ma_20:
        trend_stack_score += 1.0
    if ma_20 is not None and ma_50 is not None and ma_20 > ma_50:
        trend_stack_score += 1.0
    if close is not None and ma_50 is not None and close > ma_50:
        trend_stack_score += 1.0

    momentum_accel_5_20 = None
    if ret_5 is not None and ret_20 is not None:
        momentum_accel_5_20 = ret_5 - ret_20

    range_position_20 = _range_position_pct(close, low_20, high_20)
    range_position_60 = _range_position_pct(close, low_60, high_60)

    volume_ratio_5_20 = _ratio(avg_volume_5, avg_volume_20)
    value_ratio_5_20 = _ratio(avg_value_5, avg_value_20)

    volume_cv_20 = _cv_pct(volumes[-20:])
    value_cv_20 = _cv_pct(values[-20:])

    liquidity_log_value_20 = None
    if avg_value_20 is not None and avg_value_20 > 0:
        liquidity_log_value_20 = math.log10(avg_value_20 + 1.0)

    row = [
        ret_1,
        ret_5,
        ret_10,
        ret_20,
        ma_5_gap,
        ma_20_gap,
        ma_50_gap,
        volatility_20,
        atr_20,
        volume_ratio,
        value_ratio,
        dist_high_20,
        dist_low_20,
        range_today,
        positive_share_5,
        positive_share_10,
        positive_share_20,
        trend_stack_score,
        momentum_accel_5_20,
        range_position_20,
        range_position_60,
        dist_high_60,
        dist_low_60,
        volume_ratio_5_20,
        value_ratio_5_20,
        volume_cv_20,
        value_cv_20,
        liquidity_log_value_20,
    ]

    if any(value is None for value in row):
        return None

    return [round(float(value), 6) for value in row]


def _label_target_before_stop(
    candles: list[Candle],
    index: int,
    target_pct: float,
    stop_pct: float,
    horizon: int,
) -> int | None:
    close = _safe_float(candles[index].close)
    if close is None or close <= 0:
        return None

    target_price = close * (1.0 + target_pct)
    stop_price = close * (1.0 - stop_pct)

    for future in candles[index + 1: index + horizon + 1]:
        high = _safe_float(future.high)
        low = _safe_float(future.low)

        hit_stop = low is not None and low <= stop_price
        hit_target = high is not None and high >= target_price

        if hit_target and not hit_stop:
            return 1
        if hit_stop and not hit_target:
            return 0
        if hit_target and hit_stop:
            return 0

    return 0


def get_candles_for_ticker(db: Session, ticker: str) -> list[Candle]:
    return list(
        db.scalars(
            select(Candle)
            .where(Candle.ticker == ticker.upper().strip())
            .order_by(Candle.trade_date)
        ).all()
    )


def build_latest_feature_vector(
    db: Session,
    ticker: str,
    min_history: int = 60,
) -> dict[str, Any]:
    candles = get_candles_for_ticker(db, ticker)

    if len(candles) < min_history:
        return {
            "ok": False,
            "reason": "not_enough_candles",
            "candles_count": len(candles),
            "features": None,
        }

    features = _feature_row(candles, len(candles) - 1)

    if features is None:
        return {
            "ok": False,
            "reason": "feature_build_failed",
            "candles_count": len(candles),
            "features": None,
        }

    return {
        "ok": True,
        "ticker": ticker.upper().strip(),
        "trade_date": str(candles[-1].trade_date),
        "candles_count": len(candles),
        "feature_set": FEATURE_SET_VERSION,
        "feature_names": FEATURE_NAMES,
        "features": features,
    }


def build_ml_signal_dataset(
    db: Session,
    target_pct: float = 0.04,
    stop_pct: float = 0.025,
    horizon: int = 20,
    min_history: int = 60,
    max_tickers: int = 500,
    max_samples: int = 60_000,
) -> dict[str, Any]:
    tickers = list(
        db.scalars(
            select(Instrument.ticker)
            .where(Instrument.is_signal_eligible.is_(True))
            .where(Instrument.ticker.in_(select(Candle.ticker).distinct()))
            .order_by(Instrument.ticker)
            .limit(max_tickers)
        ).all()
    )

    X: list[list[float]] = []
    y: list[int] = []
    dates: list[str] = []
    sample_tickers: list[str] = []

    skipped_tickers = 0

    for ticker in tickers:
        candles = get_candles_for_ticker(db, ticker)

        if len(candles) < min_history + horizon + 1:
            skipped_tickers += 1
            continue

        for index in range(min_history, len(candles) - horizon):
            features = _feature_row(candles, index)
            label = _label_target_before_stop(
                candles=candles,
                index=index,
                target_pct=target_pct,
                stop_pct=stop_pct,
                horizon=horizon,
            )

            if features is None or label is None:
                continue

            X.append(features)
            y.append(label)
            dates.append(str(candles[index].trade_date))
            sample_tickers.append(ticker)

            if len(X) >= max_samples:
                break

        if len(X) >= max_samples:
            break

    positive = sum(y)
    total = len(y)

    return {
        "ok": total > 0,
        "feature_set": FEATURE_SET_VERSION,
        "feature_names": FEATURE_NAMES,
        "X": X,
        "y": y,
        "dates": dates,
        "tickers": sample_tickers,
        "summary": {
            "samples": total,
            "positive": positive,
            "negative": total - positive,
            "positive_rate_pct": round(positive / total * 100, 2) if total else None,
            "tickers_used": len(set(sample_tickers)),
            "tickers_seen": len(tickers),
            "skipped_tickers": skipped_tickers,
            "target_pct": target_pct,
            "stop_pct": stop_pct,
            "horizon": horizon,
            "min_history": min_history,
            "feature_set": FEATURE_SET_VERSION,
            "feature_count": len(FEATURE_NAMES),
        },
    }
