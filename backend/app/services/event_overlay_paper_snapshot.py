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


def _position_size(row: dict[str, Any]) -> float | None:
    direct = _to_float(row.get("base_position_size_pct"))
    if direct is not None:
        return direct
    sizing = row.get("position_sizing") or {}
    return _to_float(sizing.get("max_position_pct"))


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
        base_size = _position_size(base_row)
        adjusted = _to_float(row.get("event_adjusted_position_size_pct"))
        multiplier = _to_float(row.get("event_risk_position_multiplier")) or 1.0
        if adjusted is None and base_size is not None:
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
                "base_position_size_pct": _round(base_size, 2) if base_size is not None else None,
                "event_adjusted_position_size_pct": _round(adjusted, 2) if adjusted is not None else None,
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
            "risk_level_counts": dict(level_counts),
            "elevated_or_higher_count": sum(level_counts.get(level, 0) for level in ["elevated", "high", "extreme"]),
            "changed_actions": sum(1 for row in rows if row.get("action_changed")),
            "paper_trading_note": PAPER_TRADING_NOTE,
        },
        "rows": rows,
        "top_risk_rows": sorted(rows, key=lambda row: _to_float(row.get("event_risk_score")) or 0.0, reverse=True)[:25],
        "limitations": [
            "Read-only current snapshot; no writes and no trades.",
            "Exposure fields may be null when the base risk layer does not provide a position size.",
            "Research/paper-trading only; production defaults are unchanged.",
            "No investment advice.",
        ],
    }
