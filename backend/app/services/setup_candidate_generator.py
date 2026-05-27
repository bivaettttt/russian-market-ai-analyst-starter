from __future__ import annotations

from typing import Any

from app.services.consumer_signals import _round, _to_float
from app.services.ml_v2_dataset import _safe_number, _technical_features


SETUP_FAMILIES = [
    "breakout",
    "pullback",
    "mean_reversion",
    "momentum_continuation",
    "volatility_squeeze",
    "trend_following",
    "blue_chip_liquidity",
    "low_volatility_quality",
    "oversold_rebound",
    "regime_supported_long",
]


def _confidence(score: float) -> str:
    if score >= 75:
        return "high"
    if score >= 50:
        return "medium"
    return "low"


def _row(active: bool, score: float, reason: str, features: dict[str, Any]) -> dict[str, Any]:
    bounded = max(0.0, min(100.0, score))
    return {
        "active": bool(active),
        "score": _round(bounded, 2),
        "confidence": _confidence(bounded),
        "reason": reason,
        "features": {key: _round(value, 4) if isinstance(value, (int, float)) else value for key, value in features.items()},
    }


def pick_primary_setup_family(setups: dict[str, Any]) -> str | None:
    active = [
        (name, _to_float(row.get("score")) or 0.0)
        for name, row in setups.items()
        if isinstance(row, dict) and row.get("active")
    ]
    if not active:
        return None
    name, score = max(active, key=lambda item: item[1])
    return name if score >= 45 else None


def classify_setup_families(
    candles: list[dict[str, Any]],
    *,
    index: int | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    warnings: list[str] = []
    if index is None:
        history = list(candles)
    else:
        history = list(candles[: index + 1])
    if len(history) < 60:
        return {
            "ok": False,
            "setups": {name: _row(False, 0, "Not enough candles for setup classification.", {}) for name in SETUP_FAMILIES},
            "active_setup_families": [],
            "primary_setup_family": None,
            "setup_score": 0.0,
            "warnings": ["not_enough_candles"],
        }

    cfg = config or {}
    features = _technical_features(history)
    close = _safe_number(history[-1].get("close"))
    highs_20 = [_to_float(row.get("high")) for row in history[-20:] if _to_float(row.get("high")) is not None]
    lows_20 = [_to_float(row.get("low")) for row in history[-20:] if _to_float(row.get("low")) is not None]
    highs_60 = [_to_float(row.get("high")) for row in history[-60:] if _to_float(row.get("high")) is not None]
    lows_60 = [_to_float(row.get("low")) for row in history[-60:] if _to_float(row.get("low")) is not None]
    high_20, low_20 = max(highs_20), min(lows_20)
    high_60, low_60 = max(highs_60), min(lows_60)
    range_width_20_pct = (high_20 / low_20 - 1.0) * 100 if low_20 else 0.0
    range_width_60_pct = (high_60 / low_60 - 1.0) * 100 if low_60 else 0.0
    close_vs_sma20 = features["ma_20_gap_pct"]
    close_vs_sma50 = features["ma_50_gap_pct"]
    sma20_vs_sma50 = close_vs_sma20 - close_vs_sma50
    avg_value_20 = sum(_safe_number(row.get("value")) for row in history[-20:]) / 20

    ret_1 = features["ret_1"]
    ret_5 = features["ret_5"]
    ret_10 = features["ret_10"]
    ret_20 = features["ret_20"]
    volatility = features["volatility_20_pct"]
    volume_ratio = features["volume_ratio_20"]
    value_ratio = features["value_ratio_20"]
    range_pos_20 = features["range_position_20_pct"]
    dist_high_20 = features["dist_high_20_pct"]
    dist_high_60 = features["dist_high_60_pct"]
    dist_low_20 = features["dist_low_20_pct"]
    dist_low_60 = features["dist_low_60_pct"]
    liquidity_log = features["liquidity_log_value_20"]

    breakout_dist = _safe_number(cfg.get("breakout_dist_high_pct"), 2.0)
    breakout_volume = _safe_number(cfg.get("breakout_volume_ratio"), 1.1)
    pullback_ret_floor = _safe_number(cfg.get("pullback_ret_5_floor"), -3.0)
    mean_reversion_low = _safe_number(cfg.get("mean_reversion_dist_low_pct"), 2.0)
    squeeze_max_vol = _safe_number(cfg.get("volatility_squeeze_max_volatility"), 3.0)

    setups: dict[str, Any] = {}
    breakout_active = dist_high_20 <= breakout_dist and dist_high_60 <= breakout_dist * 1.8 and close_vs_sma20 > 0 and ret_5 > 0 and volume_ratio >= breakout_volume
    setups["breakout"] = _row(
        breakout_active,
        35 + max(0, 10 - dist_high_20 * 3) + max(0, close_vs_sma20 * 2) + min(20, volume_ratio * 8) + max(0, ret_5 * 2),
        "Close is near recent highs with positive momentum and volume confirmation.",
        {"dist_high_20_pct": dist_high_20, "dist_high_60_pct": dist_high_60, "close_vs_sma20_pct": close_vs_sma20, "volume_ratio_20": volume_ratio},
    )

    pullback_active = (close_vs_sma50 > 0 or sma20_vs_sma50 > 0) and pullback_ret_floor <= ret_5 <= 1.0 and abs(close_vs_sma20) <= 3.0 and volatility < 4.5
    setups["pullback"] = _row(
        pullback_active,
        35 + max(0, 15 - abs(close_vs_sma20) * 4) + max(0, ret_20) + max(0, 4 - volatility) * 6,
        "Broader trend is positive while price pulls back near moving-average support.",
        {"close_vs_sma20_pct": close_vs_sma20, "close_vs_sma50_pct": close_vs_sma50, "ret_5": ret_5, "ret_20": ret_20, "volatility_20_pct": volatility},
    )

    mean_active = dist_low_20 <= mean_reversion_low and dist_low_60 <= mean_reversion_low * 2 and ret_5 < 0 and ret_10 < 0 and volatility < 5.5 and ret_20 > -15
    setups["mean_reversion"] = _row(
        mean_active,
        30 + max(0, 12 - dist_low_20 * 3) + max(0, -ret_5 * 2) + max(0, 5 - volatility) * 5,
        "Price is near recent lows after short-term weakness without extreme volatility.",
        {"dist_low_20_pct": dist_low_20, "dist_low_60_pct": dist_low_60, "ret_5": ret_5, "ret_20": ret_20, "range_position_20_pct": range_pos_20},
    )

    momentum_active = ret_5 > 1 and ret_20 > 2 and close_vs_sma20 > 0 and close_vs_sma50 > 0 and volume_ratio >= 1.0
    setups["momentum_continuation"] = _row(
        momentum_active,
        30 + min(25, ret_5 * 4) + min(25, ret_20 * 1.5) + min(15, volume_ratio * 5),
        "Positive 5/20-day momentum with price above moving averages.",
        {"ret_5": ret_5, "ret_20": ret_20, "ma_20_gap_pct": close_vs_sma20, "ma_50_gap_pct": close_vs_sma50, "volume_ratio_20": volume_ratio},
    )

    squeeze_active = volatility <= squeeze_max_vol and range_width_20_pct <= max(5, range_width_60_pct * 0.55) and range_pos_20 >= 55
    setups["volatility_squeeze"] = _row(
        squeeze_active,
        35 + max(0, squeeze_max_vol - volatility) * 10 + max(0, range_pos_20 - 50) * 0.5,
        "Low realized volatility and compressed range with close in upper half.",
        {"volatility_20_pct": volatility, "range_width_20_pct": range_width_20_pct, "range_width_60_pct": range_width_60_pct, "range_position_20_pct": range_pos_20},
    )

    trend_active = close_vs_sma20 > 0 and sma20_vs_sma50 > 0 and ret_20 > 1 and dist_high_60 <= 8
    setups["trend_following"] = _row(
        trend_active,
        35 + max(0, sma20_vs_sma50 * 2) + max(0, close_vs_sma20 * 2) + min(25, ret_20 * 2) + max(0, 8 - dist_high_60),
        "Price is above an aligned SMA20/SMA50 trend with positive 20-day return.",
        {"sma20_vs_sma50_pct": sma20_vs_sma50, "close_vs_sma20_pct": close_vs_sma20, "ret_20": ret_20, "dist_high_60_pct": dist_high_60},
    )

    liquid_active = avg_value_20 >= _safe_number(cfg.get("blue_chip_min_value"), 500_000_000) and volatility < 4.5
    setups["blue_chip_liquidity"] = _row(
        liquid_active,
        30 + min(35, liquidity_log * 3) + max(0, 5 - volatility) * 5,
        "High traded value and non-extreme volatility.",
        {"avg_value_20": avg_value_20, "liquidity_log_value_20": liquidity_log, "volatility_20_pct": volatility},
    )

    low_vol_active = volatility <= 3.0 and avg_value_20 >= 50_000_000 and ret_5 > -3
    setups["low_volatility_quality"] = _row(
        low_vol_active,
        35 + max(0, 4 - volatility) * 10 + min(20, liquidity_log * 2) + max(0, ret_5),
        "Low/medium volatility, adequate liquidity, and no large recent selloff.",
        {"volatility_20_pct": volatility, "ret_5": ret_5, "avg_value_20": avg_value_20, "liquidity_log_value_20": liquidity_log},
    )

    rebound_active = ret_5 <= -3 and ret_10 <= -4 and dist_low_20 <= 4 and ret_1 > 0 and avg_value_20 >= 50_000_000
    setups["oversold_rebound"] = _row(
        rebound_active,
        30 + max(0, -ret_5 * 3) + max(0, 8 - dist_low_20) + max(0, ret_1 * 5),
        "Short-term oversold move with a positive last candle bounce.",
        {"ret_1": ret_1, "ret_5": ret_5, "dist_low_20_pct": dist_low_20, "range_position_20_pct": range_pos_20},
    )

    regime = str((cfg.get("market_regime") or cfg.get("regime") or "unknown")).lower()
    regime_score = _safe_number(cfg.get("market_regime_score") or cfg.get("regime_score"))
    regime_active = regime in {"risk_on", "neutral"} and regime != "risk_off"
    setups["regime_supported_long"] = _row(
        regime_active,
        45 + (20 if regime == "risk_on" else 5) + max(0, min(20, regime_score / 5)),
        "Market regime is not risk_off and broad context supports long candidates." if regime_active else "Market regime is unavailable or not supportive.",
        {"market_regime": regime, "market_regime_score": regime_score},
    )

    active = [name for name, row in setups.items() if row.get("active")]
    primary = pick_primary_setup_family(setups)
    score = max([_to_float(row.get("score")) or 0.0 for row in setups.values() if row.get("active")] or [0.0])
    return {
        "ok": True,
        "setups": setups,
        "active_setup_families": active,
        "primary_setup_family": primary,
        "setup_score": _round(score, 2),
        "warnings": warnings,
    }
