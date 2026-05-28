from __future__ import annotations

from collections import Counter
from statistics import mean
from typing import Any

from sqlalchemy.orm import Session

from app.services.consumer_signals import (
    _round,
    _to_float,
    list_consumer_signals,
    normalize_conservative_event_overlay_mode,
)
from app.services.event_aware_risk_overlay import get_conservative_event_risk_overlay_config


PAPER_TRADING_NOTE = (
    "Conservative event overlay is research/paper-trading only. It adjusts diagnostic exposure, "
    "does not place trades and is not investment advice."
)
DEFAULT_PAPER_POSITION_SIZE_PCT = 1.0


def _positive_size(value: Any) -> float | None:
    number = _to_float(value)
    return number if number is not None and number > 0 else None


def resolve_paper_position_size(row: dict[str, Any]) -> tuple[float, str]:
    for key in [
        "base_position_size_pct",
        "position_size_pct",
        "recommended_position_size_pct",
        "recommended_position_size",
    ]:
        direct = _positive_size(row.get(key))
        if direct is not None:
            return direct, "signal"
    sizing = row.get("position_sizing") or {}
    for key in ["position_size_pct", "recommended_position_size_pct", "max_position_pct"]:
        nested = _positive_size(sizing.get(key))
        if nested is not None:
            return nested, "signal"
    return DEFAULT_PAPER_POSITION_SIZE_PCT, "fallback_default"


def _avg(values: list[float]) -> float | None:
    return _round(mean(values), 3) if values else None


def build_event_overlay_paper_snapshot(
    db: Session,
    *,
    limit: int = 100,
    candles_limit: int = 240,
    conservative_event_overlay_mode: str = "soft_adjust",
) -> dict[str, Any]:
    overlay_mode = normalize_conservative_event_overlay_mode(conservative_event_overlay_mode)
    config = get_conservative_event_risk_overlay_config()
    baseline = list_consumer_signals(db=db, limit=limit, candles_limit=candles_limit)
    overlay = list_consumer_signals(
        db=db,
        limit=limit,
        candles_limit=candles_limit,
        use_conservative_event_overlay=True,
        conservative_event_overlay_mode=overlay_mode,
    )
    baseline_by_ticker = {row.get("ticker"): row for row in baseline.get("rows") or [] if row.get("ticker")}
    rows: list[dict[str, Any]] = []
    for row in overlay.get("rows") or []:
        ticker = row.get("ticker")
        base_row = baseline_by_ticker.get(ticker) or {}
        base_size, position_size_source = resolve_paper_position_size(base_row)
        adjusted = _to_float(row.get("event_adjusted_position_size_pct"))
        multiplier = _to_float(row.get("event_risk_position_multiplier")) or 1.0
        if adjusted is None or adjusted <= 0:
            adjusted = base_size * multiplier
        rows.append(
            {
                "ticker": ticker,
                "action": row.get("action"),
                "recommendation": row.get("recommendation"),
                "price": row.get("price"),
                "trade_date": row.get("trade_date"),
                "target_price": row.get("target_price"),
                "stop_loss": row.get("stop_loss") or (row.get("position_sizing") or {}).get("stop_loss"),
                "target_probability_pct": row.get("target_probability_pct"),
                "risk_reward_ratio": row.get("risk_reward_ratio"),
                "sector": row.get("sector"),
                "market_regime": row.get("market_regime"),
                "base_position_size_pct": _round(base_size, 2),
                "event_adjusted_position_size_pct": _round(adjusted, 2),
                "overlay_position_size_pct": _round(adjusted, 2),
                "event_position_delta_pct": _round(adjusted - base_size, 2),
                "position_size_source": position_size_source,
                "event_risk_multiplier": _round(multiplier, 3),
                "event_risk_level": row.get("event_risk_level"),
                "event_risk_score": row.get("event_risk_score"),
                "top_reasons": (row.get("event_risk_reasons") or [])[:3],
                "matched_rule_ids": row.get("event_risk_matched_rule_ids") or [],
                "action_changed": bool(row.get("event_risk_final_action_changed")),
            }
        )
    baseline_exposures = [_to_float(row.get("base_position_size_pct")) for row in rows if _to_float(row.get("base_position_size_pct")) is not None]
    overlay_exposures = [
        _to_float(row.get("event_adjusted_position_size_pct"))
        for row in rows
        if _to_float(row.get("event_adjusted_position_size_pct")) is not None
    ]
    baseline_total = sum(baseline_exposures)
    overlay_total = sum(overlay_exposures)
    multipliers = [_to_float(row.get("event_risk_multiplier")) or 1.0 for row in rows]
    source_counts = Counter(str(row.get("position_size_source") or "unknown") for row in rows)
    level_counts = Counter(str(row.get("event_risk_level") or "unknown") for row in rows)
    return {
        "ok": True,
        "mode": "conservative_event_overlay_paper_snapshot",
        "summary": {
            "rows": len(rows),
            "config_id": config.get("config_id"),
            "overlay_mode": overlay_mode,
            "baseline_total_exposure": _round(baseline_total, 2),
            "overlay_total_exposure": _round(overlay_total, 2),
            "exposure_reduction_pct": _round((1 - overlay_total / baseline_total) * 100, 2) if baseline_total > 0 else None,
            "avg_multiplier": _avg(multipliers),
            "position_size_source": "fallback_default" if source_counts.get("fallback_default", 0) else "signal",
            "position_size_source_counts": dict(source_counts),
            "default_paper_position_size_pct": DEFAULT_PAPER_POSITION_SIZE_PCT,
            "risk_level_counts": dict(level_counts),
            "elevated_or_higher_count": sum(level_counts.get(level, 0) for level in ["elevated", "high", "extreme"]),
            "changed_actions": sum(1 for row in rows if row.get("action_changed")),
            "paper_trading_note": PAPER_TRADING_NOTE,
        },
        "rows": rows,
        "top_risk_rows": sorted(rows, key=lambda row: _to_float(row.get("event_risk_score")) or 0.0, reverse=True)[:25],
        "limitations": [
            "Read-only current snapshot; no writes and no trades.",
            "If the base risk layer does not provide a position size, paper accounting uses a 1.0% fallback notional per row.",
            "Research/paper-trading only; production defaults are unchanged.",
            "No investment advice.",
        ],
    }
