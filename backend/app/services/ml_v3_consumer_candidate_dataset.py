from __future__ import annotations

import math
from collections import Counter
from typing import Any

from sqlalchemy.orm import Session

from app.services.adaptive_trade_calibration import aggregate_trade_pnl_metrics
from app.services.candidate_filter_calibration import _apply_trade_policy
from app.services.consumer_signal_backtest_audit import _build_proxy_samples
from app.services.consumer_signals import ML_V2_LONG_CANDIDATE_ACTIONS, _round, _to_float
from app.services.ml_v2_dataset import (
    DEFAULT_POLICY_ID,
    _encoded_bucket,
    _safe_number,
    _stable_text_code,
    _technical_features,
)


FEATURE_SET_VERSION = "v3_consumer_candidate_features"
DEFAULT_LONG_CANDIDATE_ACTIONS = set(ML_V2_LONG_CANDIDATE_ACTIONS)

FEATURE_NAMES = [
    "target_probability_pct",
    "rule_probability_pct",
    "ml_probability_pct",
    "ml_weight",
    "risk_reward_ratio",
    "reliability_score",
    "audit_overall_score",
    "audit_confidence_encoded",
    "action_encoded",
    "recommendation_tone_encoded",
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
    "target_pct",
    "stop_pct",
    "target_stop_ratio",
    "setup_rr",
    "policy_id_encoded",
    "atr_pct",
    "market_regime_encoded",
    "historical_regime_score",
    "downside_pressure",
    "breadth_score",
    "trend_score",
    "market_regime_adjustment_pct",
    "ticker_news_adjustment_pct",
    "global_event_adjustment_pct",
    "news_adjustment_pct",
    "macro_flags_count",
    "asset_type_encoded",
    "sector_encoded",
    "liquidity_bucket_encoded",
    "volatility_bucket_encoded",
]


def is_consumer_long_candidate_action(action: str | None, *, include_watch_candidates: bool = False) -> bool:
    normalized = str(action or "").strip().lower()
    if normalized in DEFAULT_LONG_CANDIDATE_ACTIONS:
        return True
    return bool(include_watch_candidates and normalized == "watch")


def _rate(count: int, total: int) -> float | None:
    return _round(count / total * 100, 2) if total else None


def _clean_feature(value: Any) -> float:
    number = _to_float(value)
    if number is None or math.isnan(number) or math.isinf(number):
        return 0.0
    return round(float(number), 6)


def _recommendation_tone(value: Any) -> float:
    text = str(value or "").lower()
    if "покуп" in text or "buy" in text:
        return 1.0
    if "не" in text or "avoid" in text:
        return -1.0
    if "наблю" in text or "watch" in text:
        return 0.25
    return 0.0


def _action_code(action: Any) -> float:
    mapping = {
        "buy": 1.0,
        "consider_buy": 0.8,
        "watch_ml_confirmed": 0.55,
        "buy_watch": 0.7,
        "watch_buy": 0.7,
        "watch": 0.25,
    }
    return mapping.get(str(action or "").lower(), 0.0)


def _confidence_code(value: Any) -> float:
    text = str(value or "").lower()
    if "high" in text or "выс" in text:
        return 1.0
    if "medium" in text or "сред" in text:
        return 0.5
    if "low" in text or "низ" in text:
        return -0.5
    return 0.0


def build_ml_v3_consumer_candidate_feature_row(sample: dict[str, Any], *, policy_id: str = DEFAULT_POLICY_ID) -> list[float]:
    history = sample.get("history") if isinstance(sample.get("history"), list) else []
    technical = _technical_features(history)
    market_regime = sample.get("market_regime") if isinstance(sample.get("market_regime"), dict) else {}
    components = market_regime.get("components") if isinstance(market_regime.get("components"), dict) else {}
    target_pct = abs(_safe_number(sample.get("target_return_pct") or sample.get("target_pct")))
    stop_pct = abs(_safe_number(sample.get("stop_return_pct") or sample.get("stop_pct")))
    features = {
        **technical,
        "target_probability_pct": _safe_number(sample.get("target_probability_pct") or sample.get("probability_pct")),
        "rule_probability_pct": _safe_number(sample.get("rule_probability_pct") or sample.get("probability_pct")),
        "ml_probability_pct": _safe_number(sample.get("ml_probability_pct") or sample.get("proxy_ml_probability_pct")),
        "ml_weight": _safe_number(sample.get("ml_weight")),
        "risk_reward_ratio": _safe_number(sample.get("risk_reward_ratio")),
        "reliability_score": _safe_number(sample.get("reliability_score") or sample.get("probability_pct")),
        "audit_overall_score": _safe_number(sample.get("audit_overall_score") or sample.get("audit_score")),
        "audit_confidence_encoded": _confidence_code(sample.get("audit_confidence") or sample.get("audit_confidence_level")),
        "action_encoded": _action_code(sample.get("baseline_action") or sample.get("action")),
        "recommendation_tone_encoded": _recommendation_tone(sample.get("baseline_recommendation") or sample.get("recommendation")),
        "target_pct": target_pct,
        "stop_pct": stop_pct,
        "target_stop_ratio": target_pct / stop_pct if stop_pct > 0 else 0.0,
        "setup_rr": _safe_number(sample.get("risk_reward_ratio")),
        "policy_id_encoded": _stable_text_code(policy_id, modulo=113),
        "atr_pct": _safe_number(sample.get("atr_pct")),
        "market_regime_encoded": _encoded_bucket(sample.get("market_regime_name") or market_regime.get("regime"), {"risk_off": -1, "neutral": 0, "risk_on": 1, "unknown": 0}),
        "historical_regime_score": _safe_number(sample.get("market_regime_score") or market_regime.get("regime_score")),
        "downside_pressure": _safe_number(components.get("downside_pressure")),
        "breadth_score": _safe_number(components.get("breadth_score")),
        "trend_score": _safe_number(components.get("trend_score")),
        "market_regime_adjustment_pct": _safe_number(sample.get("market_regime_adjustment_pct")),
        "ticker_news_adjustment_pct": _safe_number(sample.get("ticker_news_adjustment_pct")),
        "global_event_adjustment_pct": _safe_number(sample.get("global_event_adjustment_pct")),
        "news_adjustment_pct": _safe_number(sample.get("news_adjustment_pct")),
        "macro_flags_count": float(len(sample.get("macro_regime_flags") or [])) if isinstance(sample.get("macro_regime_flags"), list) else 0.0,
        "asset_type_encoded": _stable_text_code(sample.get("asset_type"), modulo=17),
        "sector_encoded": _stable_text_code(sample.get("sector")),
        "liquidity_bucket_encoded": _encoded_bucket(sample.get("liquidity_bucket"), {"low": 1, "medium": 2, "high": 3, "unknown": 0}),
        "volatility_bucket_encoded": _encoded_bucket(sample.get("volatility_bucket"), {"low": 1, "medium": 2, "high": 3, "extreme": 4, "unknown": 0}),
    }
    return [_clean_feature(features.get(name)) for name in FEATURE_NAMES]


def build_ml_v3_consumer_candidate_dataset(
    db: Session,
    *,
    max_tickers: int = 120,
    max_samples: int = 10000,
    min_history: int = 80,
    horizon: int = 30,
    policy_id: str = DEFAULT_POLICY_ID,
    commission_bps: float = 10.0,
    slippage_bps: float = 5.0,
    include_watch_candidates: bool = False,
) -> dict[str, Any]:
    warnings: list[str] = ["Historical consumer actions are proxy reconstructed."]
    limitations = [
        "Research-only dataset; production consumer logic is unchanged.",
        "Historical consumer actions are proxy reconstructed from daily candles.",
        "Labels use simplified target/stop simulation and costs.",
        "Daily candles cannot fully resolve intraday target/stop ordering.",
        "Historical news and macro features are sparse/proxy and default to zero when unavailable.",
    ]
    use_best_policy = policy_id == DEFAULT_POLICY_ID
    if not use_best_policy:
        warnings.append(f"Unsupported policy_id={policy_id}; using fixed 5/3/horizon fallback.")

    base_samples, tickers_seen = _build_proxy_samples(
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
    policy_samples, policy_warnings, policy = _apply_trade_policy(
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
    labels: dict[str, list[Any]] = {
        "positive_trade_return": [],
        "good_trade": [],
        "avoid_loss": [],
        "target_hit": [],
        "avoid_stop": [],
        "trade_return_pct": [],
        "outcome": [],
    }
    rows: list[dict[str, Any]] = []
    action_counts: Counter[str] = Counter()

    for sample in policy_samples[:max_samples]:
        action = str(sample.get("baseline_action") or sample.get("action") or "unknown")
        if not is_consumer_long_candidate_action(action, include_watch_candidates=include_watch_candidates):
            continue
        trade_return = _to_float(sample.get("trade_return_pct"))
        if trade_return is None:
            continue
        outcome = str(sample.get("outcome") or "unknown")
        feature_sample = {
            **sample,
            "baseline_action": action,
            "baseline_recommendation": sample.get("recommendation"),
            "target_probability_pct": sample.get("probability_pct"),
            "ml_probability_pct": sample.get("proxy_ml_probability_pct"),
            "audit_confidence": sample.get("audit_confidence_level"),
        }
        features = build_ml_v3_consumer_candidate_feature_row(feature_sample, policy_id=policy_id)
        X.append(features)
        labels["positive_trade_return"].append(1 if trade_return > 0 else 0)
        labels["good_trade"].append(1 if trade_return >= 0.5 else 0)
        labels["avoid_loss"].append(1 if trade_return >= -0.3 else 0)
        labels["target_hit"].append(1 if outcome == "target_hit" else 0)
        labels["avoid_stop"].append(1 if outcome != "stop_hit" else 0)
        labels["trade_return_pct"].append(_round(trade_return, 4) or 0.0)
        labels["outcome"].append(outcome)
        action_counts[action] += 1
        rows.append(
            {
                "ticker": sample.get("ticker"),
                "date": sample.get("date"),
                "baseline_action": action,
                "baseline_recommendation": sample.get("recommendation"),
                "target_probability_pct": sample.get("probability_pct"),
                "ml_probability_pct": sample.get("proxy_ml_probability_pct"),
                "risk_reward_ratio": sample.get("risk_reward_ratio"),
                "market_regime": sample.get("market_regime_name"),
                "audit_confidence": sample.get("audit_confidence_level"),
                "trade_return_pct": _round(trade_return, 4),
                "outcome": outcome,
                "target_pct": sample.get("target_return_pct"),
                "stop_pct": sample.get("stop_return_pct"),
            }
        )

    total = len(rows)
    pnl = aggregate_trade_pnl_metrics(
        [{"outcome": row.get("outcome"), "trade_return_pct": row.get("trade_return_pct")} for row in rows]
    )
    summary = {
        "samples": total,
        "tickers_used": len({row.get("ticker") for row in rows if row.get("ticker")}),
        "tickers_seen": len(tickers_seen),
        "active_candidate_actions": dict(sorted(action_counts.items())),
        "positive_trade_return_rate_pct": _rate(sum(int(v) for v in labels["positive_trade_return"]), total),
        "target_hit_rate_pct": pnl.get("target_hit_rate_pct"),
        "stop_hit_rate_pct": pnl.get("stop_hit_rate_pct"),
        "win_rate_pct": pnl.get("win_rate_pct"),
        "avg_trade_return_pct": pnl.get("avg_trade_return_pct"),
        "profit_factor": pnl.get("profit_factor"),
        "policy_id": policy_id if use_best_policy else "fixed_pct",
        "policy": policy,
        "horizon": horizon,
        "min_history": min_history,
        "commission_bps": commission_bps,
        "slippage_bps": slippage_bps,
    }
    if total == 0:
        warnings.append("No consumer long-candidate samples were built. Check data coverage or include_watch_candidates.")
    return {
        "ok": total > 0,
        "mode": "ml_v3_consumer_candidate_dataset",
        "feature_set": FEATURE_SET_VERSION,
        "feature_names": FEATURE_NAMES,
        "feature_count": len(FEATURE_NAMES),
        "X": X,
        "labels": labels,
        "rows": rows,
        "dates": [str(row.get("date") or "") for row in rows],
        "summary": summary,
        "warnings": warnings,
        "limitations": limitations,
    }
