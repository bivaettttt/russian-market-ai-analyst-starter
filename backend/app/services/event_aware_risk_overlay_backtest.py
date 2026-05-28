from __future__ import annotations

from collections import defaultdict
from statistics import mean
from typing import Any

from sqlalchemy.orm import Session

from app.services.adaptive_trade_calibration import aggregate_trade_pnl_metrics
from app.services.event_aware_risk_overlay import (
    DEFAULT_STABLE_RULE_METRICS,
    build_event_aware_risk_overlay,
    normalize_event_risk_overlay_mode,
)
from app.services.event_aware_rule_search import generate_event_aware_rules, sample_matches_event_rule
from app.services.event_aware_setup_research import build_event_aware_samples
from app.services.ml_v2_dataset import DEFAULT_POLICY_ID


def _to_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _round(value: Any, digits: int = 2) -> float | None:
    number = _to_float(value)
    return round(number, digits) if number is not None else None


def _weighted_profit_factor(rows: list[dict[str, Any]]) -> float | None:
    gains = 0.0
    losses = 0.0
    for row in rows:
        ret = _to_float(row.get("trade_return_pct")) or 0.0
        weight = _to_float(row.get("position_multiplier")) or 0.0
        weighted = ret * weight
        if weighted > 0:
            gains += weighted
        elif weighted < 0:
            losses += abs(weighted)
    if losses == 0:
        return round(gains, 3) if gains > 0 else None
    return round(gains / losses, 3)


def _weighted_avg_return(rows: list[dict[str, Any]]) -> float | None:
    if not rows:
        return None
    values = [(_to_float(row.get("trade_return_pct")) or 0.0) * (_to_float(row.get("position_multiplier")) or 0.0) for row in rows]
    return _round(mean(values), 3)


def _overlay_rows(samples: list[dict[str, Any]], *, mode: str, max_rules: int = 120) -> list[dict[str, Any]]:
    rules = generate_event_aware_rules(max_rules=max_rules)
    rows: list[dict[str, Any]] = []
    for sample in samples:
        matched = []
        for rule in rules:
            if sample_matches_event_rule(sample, rule):
                enriched_rule = dict(rule)
                enriched_rule.update(DEFAULT_STABLE_RULE_METRICS.get(str(rule.get("rule_id")), {}))
                matched.append(enriched_rule)
        overlay = build_event_aware_risk_overlay(
            event_context={
                "event_family": sample.get("event_family"),
                "event_direction": sample.get("event_direction"),
                "event_confirmation": sample.get("event_confirmation"),
                "event_scope": sample.get("event_scope"),
                "event_score": sample.get("event_score"),
            },
            matched_rules=matched,
            base_probability_pct=None,
            base_risk_reward_ratio=None,
            threshold_config={"mode": mode},
        )
        row = dict(sample)
        row.update(
            {
                "overlay_mode": mode,
                "risk_score": overlay.get("risk_score"),
                "risk_level": overlay.get("risk_level"),
                "position_multiplier": 1.0 if mode == "diagnostic_only" else overlay.get("position_multiplier"),
                "matched_rules_count": overlay.get("matched_rules_count"),
                "matched_rule_ids": overlay.get("matched_rule_ids") or [],
            }
        )
        rows.append(row)
    return rows


def _mode_metrics(rows: list[dict[str, Any]], *, mode: str) -> dict[str, Any]:
    baseline = aggregate_trade_pnl_metrics(
        [{"outcome": row.get("outcome"), "trade_return_pct": row.get("trade_return_pct")} for row in rows]
    )
    multipliers = [_to_float(row.get("position_multiplier")) or 0.0 for row in rows]
    weighted_avg = _weighted_avg_return(rows)
    weighted_pf = _weighted_profit_factor(rows)
    avoided_loss = sum(
        max(0.0, -(_to_float(row.get("trade_return_pct")) or 0.0)) * (1 - (_to_float(row.get("position_multiplier")) or 0.0))
        for row in rows
    )
    missed_upside = sum(
        max(0.0, _to_float(row.get("trade_return_pct")) or 0.0) * (1 - (_to_float(row.get("position_multiplier")) or 0.0))
        for row in rows
    )
    stop_exposure = sum(
        (_to_float(row.get("position_multiplier")) or 0.0)
        for row in rows
        if row.get("outcome") == "stop_hit"
    )
    total_exposure = sum(multipliers)
    avg_multiplier = mean(multipliers) if multipliers else 0.0
    return {
        "overlay_mode": mode,
        "samples": len(rows),
        "baseline_avg_trade_return_pct": baseline.get("avg_trade_return_pct"),
        "overlay_weighted_avg_return_pct": weighted_avg,
        "baseline_profit_factor": baseline.get("profit_factor"),
        "overlay_weighted_profit_factor": weighted_pf,
        "exposure_reduction_pct": _round((1 - avg_multiplier) * 100, 2),
        "weighted_stop_hit_exposure_pct": _round(stop_exposure / total_exposure * 100, 2) if total_exposure else None,
        "risk_adjusted_return_delta_pct": _round((weighted_avg or 0.0) - (_to_float(baseline.get("avg_trade_return_pct")) or 0.0), 3),
        "avoided_loss_exposure_pct": _round(avoided_loss / len(rows), 3) if rows else None,
        "missed_upside_exposure_pct": _round(missed_upside / len(rows), 3) if rows else None,
        "avg_position_multiplier": _round(avg_multiplier, 3),
    }


def _risk_level_metrics(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[str(row.get("risk_level") or "unknown")].append(row)
    result = []
    for level, items in sorted(groups.items()):
        pnl = aggregate_trade_pnl_metrics(
            [{"outcome": row.get("outcome"), "trade_return_pct": row.get("trade_return_pct")} for row in items]
        )
        multipliers = [_to_float(row.get("position_multiplier")) or 0.0 for row in items]
        result.append(
            {
                "risk_level": level,
                "samples": len(items),
                "avg_trade_return_pct": pnl.get("avg_trade_return_pct"),
                "profit_factor": pnl.get("profit_factor"),
                "stop_hit_rate_pct": pnl.get("stop_hit_rate_pct"),
                "avg_position_multiplier": _round(mean(multipliers), 3) if multipliers else None,
            }
        )
    return result


def parse_overlay_modes(value: str | None) -> list[str] | None:
    if not value:
        return None
    modes = [normalize_event_risk_overlay_mode(item.strip()) for item in value.split(",") if item.strip()]
    modes = [mode for mode in modes if mode != "disabled"]
    return modes or None


def build_event_risk_overlay_backtest(
    db: Session,
    *,
    max_tickers: int = 120,
    max_samples: int = 10000,
    max_events: int = 10000,
    min_history: int = 80,
    horizon: int = 30,
    policy_id: str = DEFAULT_POLICY_ID,
    event_lookback_days: int = 7,
    event_decay_days: int = 14,
    overlay_modes: list[str] | None = None,
    commission_bps: float = 10.0,
    slippage_bps: float = 5.0,
    min_signals: int = 20,
) -> dict[str, Any]:
    modes = overlay_modes or ["diagnostic_only", "soft_adjust", "experimental_downgrade"]
    modes = [normalize_event_risk_overlay_mode(mode) for mode in modes if normalize_event_risk_overlay_mode(mode) != "disabled"]
    data = build_event_aware_samples(
        db,
        max_tickers=max_tickers,
        max_samples=max_samples,
        max_events=max_events,
        min_history=min_history,
        horizon=horizon,
        policy_id=policy_id,
        event_lookback_days=event_lookback_days,
        event_decay_days=event_decay_days,
        commission_bps=commission_bps,
        slippage_bps=slippage_bps,
        include_global_events=True,
        include_ticker_events=True,
    )
    if not data.get("ok"):
        return {"ok": False, "mode": "event_risk_overlay_backtest", "summary": {}, "warnings": data.get("warnings") or []}
    samples = [row for row in data.get("samples") or [] if row.get("event_family")]
    warnings = list(data.get("warnings") or [])
    if len(samples) < min_signals:
        warnings.append("event-aware samples below min_signals; overlay backtest is low confidence")
    by_mode: list[dict[str, Any]] = []
    risk_rows: list[dict[str, Any]] = []
    mode_rows: dict[str, list[dict[str, Any]]] = {}
    for mode in modes:
        rows = _overlay_rows(samples, mode=mode)
        mode_rows[mode] = rows
        by_mode.append(_mode_metrics(rows, mode=mode))
        if mode == "soft_adjust":
            risk_rows = rows
    baseline = aggregate_trade_pnl_metrics(
        [{"outcome": row.get("outcome"), "trade_return_pct": row.get("trade_return_pct")} for row in samples]
    )
    soft = next((row for row in by_mode if row.get("overlay_mode") == "soft_adjust"), by_mode[0] if by_mode else {})
    recommendation = "research_only"
    if (
        (_to_float(soft.get("overlay_weighted_profit_factor")) or 0.0) > (_to_float(soft.get("baseline_profit_factor")) or 0.0)
        and (_to_float(soft.get("risk_adjusted_return_delta_pct")) or 0.0) > 0
    ):
        recommendation = "promising_soft_overlay"
    elif (_to_float(soft.get("risk_adjusted_return_delta_pct")) or 0.0) < 0:
        recommendation = "diagnostic_only"
    return {
        "ok": True,
        "mode": "event_risk_overlay_backtest",
        "summary": {
            "samples": len(samples),
            "event_samples": len(samples),
            "baseline_avg_trade_return_pct": baseline.get("avg_trade_return_pct"),
            "baseline_profit_factor": baseline.get("profit_factor"),
            "overlay_weighted_avg_return_pct": soft.get("overlay_weighted_avg_return_pct"),
            "overlay_weighted_profit_factor": soft.get("overlay_weighted_profit_factor"),
            "exposure_reduction_pct": soft.get("exposure_reduction_pct"),
            "risk_adjusted_return_delta_pct": soft.get("risk_adjusted_return_delta_pct"),
            "recommendation": recommendation,
        },
        "by_overlay_mode": by_mode,
        "by_risk_level": _risk_level_metrics(risk_rows),
        "examples": {
            "highest_risk": sorted(risk_rows, key=lambda row: _to_float(row.get("risk_score")) or 0.0, reverse=True)[:10],
            "reduced_winners": [
                row for row in risk_rows if (_to_float(row.get("trade_return_pct")) or 0.0) > 0 and (_to_float(row.get("position_multiplier")) or 1.0) < 1.0
            ][:10],
            "reduced_losers": [
                row for row in risk_rows if (_to_float(row.get("trade_return_pct")) or 0.0) < 0 and (_to_float(row.get("position_multiplier")) or 1.0) < 1.0
            ][:10],
        },
        "warnings": warnings,
        "limitations": [
            "Overlay scoring uses fixed deterministic rules from stability diagnostics and current historical samples.",
            "This is not leakage-safe overlay walk-forward proof.",
            "Needs future paper trading before production use.",
        ],
    }
