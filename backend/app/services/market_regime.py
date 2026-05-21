from __future__ import annotations

from math import sqrt
from statistics import mean
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Candle, Instrument


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


def _candle_to_dict(candle: Candle) -> dict[str, Any]:
    return {
        "ticker": candle.ticker,
        "trade_date": candle.trade_date.isoformat() if candle.trade_date else None,
        "open": candle.open,
        "high": candle.high,
        "low": candle.low,
        "close": candle.close,
        "volume": candle.volume,
        "value": candle.value,
    }


def _daily_volatility_pct(closes: list[float]) -> float | None:
    if len(closes) < 21:
        return None
    returns: list[float] = []
    for previous, current in zip(closes[-21:-1], closes[-20:]):
        if previous:
            returns.append((current - previous) / previous * 100)
    if len(returns) < 2:
        return None
    avg = mean(returns)
    variance = sum((item - avg) ** 2 for item in returns) / (len(returns) - 1)
    return sqrt(variance)


def _ticker_metrics(candles: list[dict[str, Any]], index: int | None = None) -> dict[str, Any] | None:
    if not candles:
        return None
    end = len(candles) - 1 if index is None else min(index, len(candles) - 1)
    if end < 20:
        return None
    history = candles[: end + 1]
    closes = [_to_float(row.get("close")) for row in history if _to_float(row.get("close")) is not None]
    lows = [_to_float(row.get("low")) for row in history[-20:] if _to_float(row.get("low")) is not None]
    if len(closes) < 21:
        return None

    close = closes[-1]
    sma20 = mean(closes[-20:])
    ret5 = _pct_change(close, closes[-6]) if len(closes) >= 6 else None
    ret20 = _pct_change(close, closes[-21]) if len(closes) >= 21 else None
    low20 = min(lows) if lows else None
    near_20d_low = bool(low20 and close <= low20 * 1.03)
    volatility20 = _daily_volatility_pct(closes)

    return {
        "above_sma20": close > sma20,
        "ret5_positive": ret5 is not None and ret5 > 0,
        "ret20_positive": ret20 is not None and ret20 > 0,
        "ret20_below_minus5": ret20 is not None and ret20 < -5,
        "near_20d_low": near_20d_low,
        "negative_momentum": bool((ret5 is not None and ret5 < 0) and (ret20 is not None and ret20 < 0)),
        "ret5_pct": ret5,
        "ret20_pct": ret20,
        "volatility20_pct": volatility20,
    }


def _rate(count: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return count / total * 100


def _build_regime_from_metrics(
    *,
    metrics: list[dict[str, Any]],
    mode: str,
    lookback: int,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    warnings = list(warnings or [])
    sample_size = len(metrics)
    if sample_size < 10:
        warnings.append("insufficient_market_regime_data")
        return {
            "ok": True,
            "mode": mode,
            "regime": "neutral",
            "regime_score": 0.0,
            "trend_score": 0.0,
            "breadth_score": 0.0,
            "volatility_score": 0.0,
            "downside_pressure": 0.0,
            "long_allowed": True,
            "position_multiplier": 0.75,
            "min_rr_multiplier": 1.1,
            "min_ml_probability_addon": 3,
            "sample_size": sample_size,
            "lookback": lookback,
            "reasons": ["Недостаточно широкой истории рынка, режим считается neutral."],
            "warnings": warnings,
        }

    pct_above_sma20 = _rate(sum(1 for item in metrics if item["above_sma20"]), sample_size)
    pct_ret5_positive = _rate(sum(1 for item in metrics if item["ret5_positive"]), sample_size)
    pct_ret20_positive = _rate(sum(1 for item in metrics if item["ret20_positive"]), sample_size)
    pct_ret20_bad = _rate(sum(1 for item in metrics if item["ret20_below_minus5"]), sample_size)
    pct_near_low = _rate(sum(1 for item in metrics if item["near_20d_low"]), sample_size)
    pct_negative_momentum = _rate(sum(1 for item in metrics if item["negative_momentum"]), sample_size)
    vol_values = [item["volatility20_pct"] for item in metrics if item.get("volatility20_pct") is not None]
    avg_vol20 = mean(vol_values) if vol_values else 0.0
    high_vol_pct = _rate(sum(1 for item in metrics if (_to_float(item.get("volatility20_pct")) or 0) >= 4.0), sample_size)

    breadth_raw = (pct_above_sma20 * 0.45) + (pct_ret5_positive * 0.2) + (pct_ret20_positive * 0.35)
    breadth_score = _clamp((breadth_raw - 50.0) * 2.0, -100.0, 100.0)
    trend_score = _clamp(((pct_ret20_positive + pct_above_sma20) / 2.0 - 50.0) * 2.0, -100.0, 100.0)
    downside_pressure = _clamp((pct_ret20_bad * 0.45) + (pct_near_low * 0.25) + (pct_negative_momentum * 0.30), 0.0, 100.0)
    volatility_score = _clamp((avg_vol20 / 4.0 * 60.0) + (high_vol_pct * 0.40), 0.0, 100.0)
    regime_score = _clamp(
        trend_score * 0.35 + breadth_score * 0.35 - downside_pressure * 0.20 - volatility_score * 0.10,
        -100.0,
        100.0,
    )

    if regime_score >= 25:
        regime = "risk_on"
    elif regime_score <= -25:
        regime = "risk_off"
    else:
        regime = "neutral"

    long_allowed = not (regime_score <= -35 or downside_pressure >= 65)
    if regime == "risk_on":
        position_multiplier = 1.10
        min_rr_multiplier = 1.0
        min_ml_probability_addon = 0
    elif regime == "risk_off":
        position_multiplier = 0.50 if long_allowed else 0.0
        min_rr_multiplier = 1.4 if long_allowed else 1.5
        min_ml_probability_addon = 10 if long_allowed else 15
    else:
        position_multiplier = 0.90
        min_rr_multiplier = 1.1
        min_ml_probability_addon = 4

    reasons = [
        f"Ширина рынка: {pct_above_sma20:.1f}% тикеров выше SMA20, {pct_ret20_positive:.1f}% имеют положительную 20d доходность.",
        f"Downside pressure: {downside_pressure:.1f}/100, доля тикеров с ret20 < -5%: {pct_ret20_bad:.1f}%.",
        f"Средняя 20d daily volatility: {avg_vol20:.2f}%, high-vol доля: {high_vol_pct:.1f}%.",
    ]
    if regime == "risk_off":
        reasons.append("Режим risk_off: long-сигналы требуют более жёсткого risk/ML подтверждения.")
    elif regime == "risk_on":
        reasons.append("Режим risk_on: ширина и тренд рынка поддерживают long-сценарии.")
    else:
        reasons.append("Режим neutral: market filter не даёт сильного directional edge.")

    return {
        "ok": True,
        "mode": mode,
        "regime": regime,
        "regime_score": _round(regime_score, 2),
        "trend_score": _round(trend_score, 2),
        "breadth_score": _round(breadth_score, 2),
        "volatility_score": _round(volatility_score, 2),
        "downside_pressure": _round(downside_pressure, 2),
        "long_allowed": bool(long_allowed),
        "position_multiplier": _round(position_multiplier, 2),
        "min_rr_multiplier": _round(min_rr_multiplier, 2),
        "min_ml_probability_addon": min_ml_probability_addon,
        "sample_size": sample_size,
        "lookback": lookback,
        "components": {
            "pct_above_sma20": _round(pct_above_sma20, 2),
            "pct_ret5_positive": _round(pct_ret5_positive, 2),
            "pct_ret20_positive": _round(pct_ret20_positive, 2),
            "pct_ret20_below_minus5": _round(pct_ret20_bad, 2),
            "pct_near_20d_low": _round(pct_near_low, 2),
            "pct_negative_momentum": _round(pct_negative_momentum, 2),
            "avg_volatility20_pct": _round(avg_vol20, 2),
            "high_volatility_pct": _round(high_vol_pct, 2),
        },
        "reasons": reasons,
        "warnings": warnings,
    }


def build_market_regime(
    db: Session,
    lookback: int = 60,
    max_tickers: int = 120,
) -> dict[str, Any]:
    instruments = db.scalars(
        select(Instrument)
        .where(Instrument.is_signal_eligible.is_(True))
        .where(Instrument.asset_type.in_(["stock", "share", "equity", "unknown"]))
        .order_by(Instrument.ticker.asc())
        .limit(max_tickers)
    ).all()

    if not instruments:
        instruments = db.scalars(
            select(Instrument)
            .where(Instrument.asset_type.in_(["stock", "share", "equity", "unknown"]))
            .order_by(Instrument.ticker.asc())
            .limit(max_tickers)
        ).all()

    metrics: list[dict[str, Any]] = []
    warnings: list[str] = []
    candle_limit = max(lookback + 25, 85)

    for instrument in instruments:
        candles = [
            _candle_to_dict(row)
            for row in db.scalars(
                select(Candle)
                .where(Candle.ticker == instrument.ticker)
                .order_by(Candle.trade_date.desc())
                .limit(candle_limit)
            ).all()
            if row.close is not None
        ]
        candles.reverse()
        metric = _ticker_metrics(candles)
        if metric:
            metrics.append(metric)

    if not metrics:
        warnings.append("no_market_regime_candles")

    return _build_regime_from_metrics(
        metrics=metrics,
        mode="live_market_regime",
        lookback=lookback,
        warnings=warnings,
    )


def build_market_regime_for_date_proxy(
    candles_by_ticker: dict[str, list[dict[str, Any]]],
    index_by_ticker: dict[str, int],
    lookback: int = 60,
) -> dict[str, Any]:
    metrics: list[dict[str, Any]] = []
    for ticker, candles in candles_by_ticker.items():
        index = index_by_ticker.get(ticker)
        if index is None:
            continue
        history_start = max(0, index - lookback - 25)
        local_candles = candles[history_start : index + 1]
        local_index = len(local_candles) - 1
        metric = _ticker_metrics(local_candles, local_index)
        if metric:
            metrics.append(metric)

    return _build_regime_from_metrics(
        metrics=metrics,
        mode="proxy_historical_market_regime",
        lookback=lookback,
        warnings=[],
    )
