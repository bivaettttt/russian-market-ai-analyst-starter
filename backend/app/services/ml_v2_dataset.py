from __future__ import annotations

import math
from statistics import mean, pstdev
from typing import Any

from sqlalchemy.orm import Session

from app.services.candidate_filter_calibration import _apply_trade_policy
from app.services.consumer_signal_backtest_audit import _build_proxy_samples
from app.services.consumer_signals import _round, _to_float


FEATURE_SET_VERSION = "v2_trade_pnl_features"
DEFAULT_POLICY_ID = "atr_t1_5_s1_6_h30_rr0_8"

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
    "range_position_20_pct",
    "range_position_60_pct",
    "dist_high_20_pct",
    "dist_low_20_pct",
    "dist_high_60_pct",
    "dist_low_60_pct",
    "volume_ratio_20",
    "value_ratio_20",
    "liquidity_log_value_20",
    "momentum_accel_5_20",
    "volatility_bucket_encoded",
    "liquidity_bucket_encoded",
    "market_regime_encoded",
    "historical_regime_score",
    "downside_pressure",
    "breadth_score",
    "trend_score",
    "atr_pct",
    "trade_setup_target_pct",
    "trade_setup_stop_pct",
    "trade_setup_rr",
    "policy_target_atr_mult",
    "policy_stop_atr_mult",
    "sector_encoded",
    "asset_type_encoded",
]


def _safe_number(value: Any, default: float = 0.0) -> float:
    number = _to_float(value)
    if number is None or math.isnan(number) or math.isinf(number):
        return default
    return float(number)


def _avg(values: list[float]) -> float | None:
    return mean(values) if values else None


def _std(values: list[float]) -> float | None:
    return pstdev(values) if len(values) >= 2 else None


def _pct_change(current: float | None, previous: float | None) -> float | None:
    if current is None or previous in (None, 0):
        return None
    return (current / previous - 1.0) * 100.0


def _ratio(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator in (None, 0):
        return None
    return numerator / denominator


def _range_position_pct(close: float | None, low: float | None, high: float | None) -> float | None:
    if close is None or low is None or high is None or high == low:
        return None
    return (close - low) / (high - low) * 100.0


def _encoded_bucket(value: Any, mapping: dict[str, float]) -> float:
    return mapping.get(str(value or "unknown").lower(), 0.0)


def _stable_text_code(value: Any, modulo: int = 101) -> float:
    text = str(value or "unknown").lower()
    return float(sum(ord(ch) for ch in text) % modulo) / float(modulo)


def _technical_features(history: list[dict[str, Any]]) -> dict[str, float]:
    closes = [_to_float(row.get("close")) for row in history]
    highs = [_to_float(row.get("high")) for row in history]
    lows = [_to_float(row.get("low")) for row in history]
    volumes = [_to_float(row.get("volume")) for row in history]
    values = [_to_float(row.get("value")) for row in history]
    closes_clean = [value for value in closes if value is not None]
    close = closes_clean[-1] if closes_clean else None

    def close_back(days: int) -> float | None:
        if len(closes) <= days:
            return None
        return closes[-days - 1]

    ma_5 = _avg([value for value in closes[-5:] if value is not None])
    ma_20 = _avg([value for value in closes[-20:] if value is not None])
    ma_50 = _avg([value for value in closes[-50:] if value is not None])
    returns_20 = [
        _pct_change(current, previous)
        for previous, current in zip(closes[-21:-1], closes[-20:])
        if previous is not None and current is not None
    ]
    ranges_20 = []
    for row in history[-20:]:
        high = _to_float(row.get("high"))
        low = _to_float(row.get("low"))
        row_close = _to_float(row.get("close"))
        if high is not None and low is not None and row_close and row_close > 0:
            ranges_20.append((high - low) / row_close * 100.0)
    high_20_values = [value for value in highs[-20:] if value is not None]
    low_20_values = [value for value in lows[-20:] if value is not None]
    high_60_values = [value for value in highs[-60:] if value is not None]
    low_60_values = [value for value in lows[-60:] if value is not None]
    high_20 = max(high_20_values) if high_20_values else None
    low_20 = min(low_20_values) if low_20_values else None
    high_60 = max(high_60_values) if high_60_values else None
    low_60 = min(low_60_values) if low_60_values else None
    avg_volume_20 = _avg([value for value in volumes[-20:] if value is not None])
    avg_value_20 = _avg([value for value in values[-20:] if value is not None])

    return {
        "ret_1": _safe_number(_pct_change(close, close_back(1))),
        "ret_5": _safe_number(_pct_change(close, close_back(5))),
        "ret_10": _safe_number(_pct_change(close, close_back(10))),
        "ret_20": _safe_number(_pct_change(close, close_back(20))),
        "ma_5_gap_pct": _safe_number(_pct_change(close, ma_5)),
        "ma_20_gap_pct": _safe_number(_pct_change(close, ma_20)),
        "ma_50_gap_pct": _safe_number(_pct_change(close, ma_50)),
        "volatility_20_pct": _safe_number(_std([value for value in returns_20 if value is not None])),
        "atr_20_pct": _safe_number(_avg(ranges_20)),
        "range_position_20_pct": _safe_number(_range_position_pct(close, low_20, high_20), 50.0),
        "range_position_60_pct": _safe_number(_range_position_pct(close, low_60, high_60), 50.0),
        "dist_high_20_pct": _safe_number(_pct_change(high_20, close)),
        "dist_low_20_pct": _safe_number(_pct_change(close, low_20)),
        "dist_high_60_pct": _safe_number(_pct_change(high_60, close)),
        "dist_low_60_pct": _safe_number(_pct_change(close, low_60)),
        "volume_ratio_20": _safe_number(_ratio(volumes[-1] if volumes else None, avg_volume_20), 1.0),
        "value_ratio_20": _safe_number(_ratio(values[-1] if values else None, avg_value_20), 1.0),
        "liquidity_log_value_20": math.log10(avg_value_20 + 1.0) if avg_value_20 and avg_value_20 > 0 else 0.0,
        "momentum_accel_5_20": _safe_number((_pct_change(close, close_back(5)) or 0.0) - (_pct_change(close, close_back(20)) or 0.0)),
    }


def build_ml_v2_feature_row(sample: dict[str, Any]) -> list[float]:
    history = sample.get("history") if isinstance(sample.get("history"), list) else []
    technical = _technical_features(history)
    market_regime = sample.get("market_regime") if isinstance(sample.get("market_regime"), dict) else {}
    features = {
        **technical,
        "volatility_bucket_encoded": _encoded_bucket(sample.get("volatility_bucket"), {"low": 1, "medium": 2, "high": 3, "extreme": 4, "unknown": 0}),
        "liquidity_bucket_encoded": _encoded_bucket(sample.get("liquidity_bucket"), {"low": 1, "medium": 2, "high": 3, "unknown": 0}),
        "market_regime_encoded": _encoded_bucket(sample.get("market_regime_name") or market_regime.get("regime"), {"risk_off": -1, "neutral": 0, "risk_on": 1, "unknown": 0}),
        "historical_regime_score": _safe_number(sample.get("market_regime_score") or market_regime.get("regime_score")),
        "downside_pressure": _safe_number(market_regime.get("components", {}).get("downside_pressure") if isinstance(market_regime.get("components"), dict) else None),
        "breadth_score": _safe_number(market_regime.get("components", {}).get("breadth_score") if isinstance(market_regime.get("components"), dict) else None),
        "trend_score": _safe_number(market_regime.get("components", {}).get("trend_score") if isinstance(market_regime.get("components"), dict) else None),
        "atr_pct": _safe_number(sample.get("atr_pct")),
        "trade_setup_target_pct": _safe_number(sample.get("target_return_pct") or sample.get("trade_setup_target_pct")),
        "trade_setup_stop_pct": abs(_safe_number(sample.get("stop_return_pct") or sample.get("trade_setup_stop_pct"))),
        "trade_setup_rr": _safe_number(sample.get("risk_reward_ratio")),
        "policy_target_atr_mult": 1.5,
        "policy_stop_atr_mult": 1.6,
        "sector_encoded": _stable_text_code(sample.get("sector")),
        "asset_type_encoded": _stable_text_code(sample.get("asset_type"), modulo=17),
    }
    return [round(_safe_number(features.get(name)), 6) for name in FEATURE_NAMES]


def _rate(count: int, total: int) -> float | None:
    return _round(count / total * 100, 2) if total else None


def build_ml_v2_trade_dataset(
    db: Session,
    *,
    max_tickers: int = 120,
    max_samples: int = 10000,
    min_history: int = 80,
    horizon: int = 30,
    policy_id: str = DEFAULT_POLICY_ID,
    commission_bps: float = 10.0,
    slippage_bps: float = 5.0,
) -> dict[str, Any]:
    warnings: list[str] = []
    use_best_policy = policy_id == DEFAULT_POLICY_ID
    if not use_best_policy:
        warnings.append(f"Unsupported policy_id={policy_id}; using fixed 5/3/horizon fallback for research dataset.")
    base_samples, tickers_used = _build_proxy_samples(
        db=db,
        max_tickers=max_tickers,
        max_samples=max_samples,
        horizon=max(horizon, 30 if use_best_policy else horizon),
        target_pct=0.05,
        stop_pct=0.03,
        min_history=min_history,
        use_market_regime_filter=False,
        commission_bps=0.0,
        slippage_bps=0.0,
    )
    samples, policy_warnings, policy = _apply_trade_policy(
        base_samples,
        horizon=horizon,
        target_pct=0.05,
        stop_pct=0.03,
        commission_bps=commission_bps,
        slippage_bps=slippage_bps,
        use_best_adaptive_policy=use_best_policy,
    )
    warnings.extend(policy_warnings)

    X: list[list[float]] = []
    labels = {
        "positive_trade_return": [],
        "target_hit": [],
        "avoid_stop": [],
        "good_trade": [],
        "trade_return_pct": [],
    }
    rows: list[dict[str, Any]] = []

    for sample in samples[:max_samples]:
        trade_return = _to_float(sample.get("trade_return_pct"))
        if trade_return is None:
            continue
        features = build_ml_v2_feature_row(sample)
        X.append(features)
        labels["positive_trade_return"].append(1 if trade_return > 0 else 0)
        labels["target_hit"].append(1 if sample.get("outcome") == "target_hit" else 0)
        labels["avoid_stop"].append(1 if sample.get("outcome") != "stop_hit" else 0)
        labels["good_trade"].append(1 if trade_return >= 0.5 else 0)
        labels["trade_return_pct"].append(_round(trade_return, 4) or 0.0)
        rows.append(
            {
                "ticker": sample.get("ticker"),
                "date": sample.get("date"),
                "trade_return_pct": _round(trade_return, 4),
                "outcome": sample.get("outcome"),
                "target_pct": sample.get("target_return_pct"),
                "stop_pct": sample.get("stop_return_pct"),
            }
        )

    total = len(X)
    returns = labels["trade_return_pct"]
    target_hits = sum(labels["target_hit"])
    stop_hits = sum(1 for row in rows if row.get("outcome") == "stop_hit")
    positive = sum(labels["positive_trade_return"])
    summary = {
        "samples": total,
        "tickers_used": len(set(row.get("ticker") for row in rows if row.get("ticker"))),
        "tickers_seen": len(tickers_used),
        "positive_trade_return_rate_pct": _rate(positive, total),
        "target_hit_rate_pct": _rate(target_hits, total),
        "stop_hit_rate_pct": _rate(stop_hits, total),
        "avg_trade_return_pct": _round(sum(returns) / total, 2) if total else None,
        "policy_id": policy_id if use_best_policy else "fixed_pct",
        "policy": policy,
        "horizon": horizon,
        "min_history": min_history,
        "commission_bps": commission_bps,
        "slippage_bps": slippage_bps,
        "feature_count": len(FEATURE_NAMES),
    }
    if total == 0:
        warnings.append("No ML v2 samples were built. Check data coverage and min_history/horizon.")
    return {
        "ok": total > 0,
        "mode": "ml_v2_trade_dataset",
        "feature_set": FEATURE_SET_VERSION,
        "feature_names": FEATURE_NAMES,
        "X": X,
        "labels": labels,
        "rows": rows,
        "dates": [str(row.get("date") or "") for row in rows],
        "summary": summary,
        "warnings": warnings,
    }
