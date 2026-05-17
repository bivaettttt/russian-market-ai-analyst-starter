from __future__ import annotations

import math
from datetime import date
from statistics import mean, pstdev
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Candle, Instrument


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


def _avg(values: list[float]) -> float | None:
    clean = [value for value in values if value is not None]
    if not clean:
        return None
    return mean(clean)


def _std(values: list[float]) -> float | None:
    clean = [value for value in values if value is not None]
    if len(clean) < 2:
        return None
    return pstdev(clean)


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

    ma_5 = _avg([item for item in closes[-5:] if item is not None])
    ma_20 = _avg([item for item in closes[-20:] if item is not None])
    ma_50 = _avg([item for item in closes[-50:] if item is not None])

    ma_5_gap = _pct_change(close, ma_5)
    ma_20_gap = _pct_change(close, ma_20)
    ma_50_gap = _pct_change(close, ma_50)

    returns_20: list[float] = []
    for offset in range(index - 19, index + 1):
        if offset <= 0:
            continue
        r = _pct_change(_safe_float(candles[offset].close), _safe_float(candles[offset - 1].close))
        if r is not None:
            returns_20.append(r)

    volatility_20 = _std(returns_20)

    ranges_20: list[float] = []
    for item in candles[max(0, index - 19): index + 1]:
        item_high = _safe_float(item.high)
        item_low = _safe_float(item.low)
        item_close = _safe_float(item.close)
        if item_high is not None and item_low is not None and item_close and item_close > 0:
            ranges_20.append((item_high - item_low) / item_close * 100.0)

    atr_20 = _avg(ranges_20)

    avg_volume_20 = _avg([item for item in volumes[-20:] if item is not None and item > 0])
    avg_value_20 = _avg([item for item in values[-20:] if item is not None and item > 0])

    volume_ratio = volume / avg_volume_20 if volume is not None and avg_volume_20 else None
    value_ratio = value / avg_value_20 if value is not None and avg_value_20 else None

    high_20_values = [item for item in highs[-20:] if item is not None]
    low_20_values = [item for item in lows[-20:] if item is not None]

    high_20 = max(high_20_values) if high_20_values else None
    low_20 = min(low_20_values) if low_20_values else None

    dist_high_20 = _pct_change(high_20, close)
    dist_low_20 = _pct_change(close, low_20)

    range_today = None
    if high is not None and low is not None and close > 0:
        range_today = (high - low) / close * 100.0

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
        },
    }
